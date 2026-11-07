"""Mission objective types. Each one is created from a JSON dict in a mission file."""
from __future__ import annotations

import math


class Objective:
    def __init__(self, spec):
        self.spec = spec
        self.text = spec.get("text", "")
        self.marker = tuple(spec["pos"]) if spec.get("marker", True) and "pos" in spec else None

    def start(self, ctx):
        pass

    def update(self, ctx, dt):
        """Return True when complete."""
        return False

    def status(self):
        return self.text

    def finish(self, ctx):
        pass


class ReachArea(Objective):
    def update(self, ctx, dt):
        px, py, pz = ctx.player_position()
        x, y = self.spec["pos"][0], self.spec["pos"][1]
        z = self.spec["pos"][2] if len(self.spec["pos"]) > 2 else pz
        return math.hypot(px - x, py - y) <= self.spec.get("radius", 4.0) and abs(pz - z) < 3.0


class Interact(Objective):
    """Stand near a point, look at it and hold the interact key (E)."""

    def __init__(self, spec):
        super().__init__(spec)
        self.held = 0.0
        self.hold_time = float(spec.get("hold", 1.5))
        self.prompt = spec.get("prompt", "Hold E to interact")

    def update(self, ctx, dt):
        pos = self.spec["pos"]
        px, py, pz = ctx.player_eye_position()
        dist = math.dist((px, py, pz), pos)
        in_range = dist <= self.spec.get("radius", 2.5) and ctx.player_looking_at(pos, 40.0)
        if in_range:
            if ctx.interact_held():
                self.held += dt
            else:
                self.held = max(0.0, self.held - dt * 2.0)
            ctx.set_prompt(self.prompt, self.held / self.hold_time if self.held > 0 else None)
        else:
            self.held = 0.0
            ctx.set_prompt(None)
        if self.held >= self.hold_time:
            ctx.set_prompt(None)
            if self.spec.get("charge"):
                ctx.point_done(self.spec, tuple(pos))
            return True
        return False

    def finish(self, ctx):
        ctx.set_prompt(None)


class EliminateGroup(Objective):
    def start(self, ctx):
        if "pos" not in self.spec:
            self.marker = None

    def update(self, ctx, dt):
        total = ctx.group_total(self.spec["group"])
        return total > 0 and ctx.group_alive(self.spec["group"]) == 0

    def status_with(self, ctx):
        total = ctx.group_total(self.spec["group"])
        done = total - ctx.group_alive(self.spec["group"])
        return f"{self.text} ({done}/{total})" if total else self.text


class Survive(Objective):
    def __init__(self, spec):
        super().__init__(spec)
        self.remaining = float(spec["seconds"])

    def update(self, ctx, dt):
        self.remaining -= dt
        return self.remaining <= 0.0

    def status(self):
        return f"{self.text} ({max(0, int(math.ceil(self.remaining)))} s)"


class Escort(Objective):
    """Get a squad member (e.g. a wounded soldier) to the end of a route. The marker follows them."""

    def start(self, ctx):
        ctx.escort_start(self.spec["target"], self.spec["route"])
        self.marker = ctx.squad_position(self.spec["target"])

    def update(self, ctx, dt):
        pos = ctx.squad_position(self.spec["target"])
        if pos is None:
            return False
        self.marker = (pos[0], pos[1], pos[2] + 2.3)
        end = self.spec["route"][-1]
        return math.hypot(pos[0] - end[0], pos[1] - end[1]) <= self.spec.get("radius", 3.0)


class Ride(Objective):
    """Sit in a vehicle until it reaches the end of its route (you can shoot on the way)."""

    def update(self, ctx, dt):
        return ctx.ride_finished()


class Tag(Objective):
    """Tag `count` enemies with the recon drone."""

    def __init__(self, spec):
        super().__init__(spec)
        self.count = int(spec.get("count", 1))
        self.done = 0

    def update(self, ctx, dt):
        self.done = min(self.count, ctx.tagged_count())
        return self.done >= self.count

    def status(self):
        return f"{self.text} ({self.done}/{self.count})"


class DestroyVehicles(Objective):
    """Destroy the listed vehicles (helicopter, boats ...). The marker follows the first one left."""

    def __init__(self, spec):
        super().__init__(spec)
        self.targets = list(spec["targets"])
        self.done = 0

    def update(self, ctx, dt):
        left = [t for t in self.targets if not ctx.vehicle_destroyed(t)]
        self.done = len(self.targets) - len(left)
        self.marker = None
        if left and self.spec.get("marker", True):
            pos = ctx.vehicle_position(left[0])
            if pos is not None:
                self.marker = (pos[0], pos[1], pos[2] + 3.0)
        return not left

    def status(self):
        if len(self.targets) == 1:
            return self.text
        return f"{self.text} ({self.done}/{len(self.targets)})"


class VehiclesArrive(Objective):
    """Wait (and survive) until the listed vehicles reach the end of their routes."""

    def __init__(self, spec):
        super().__init__(spec)
        self.targets = list(spec["targets"])
        self.done = 0

    def update(self, ctx, dt):
        self.done = sum(1 for t in self.targets if ctx.vehicle_arrived(t))
        return self.done >= len(self.targets)

    def status(self):
        return f"{self.text} ({self.done}/{len(self.targets)})"


class InteractMulti(Objective):
    """Several points to interact with, in any order (e.g. plant charges). Marker on the nearest one left."""

    def __init__(self, spec):
        super().__init__(spec)
        self.points = [tuple(p) for p in spec["points"]]
        self.left = list(range(len(self.points)))
        self.held = 0.0
        self.hold_time = float(spec.get("hold", 2.0))
        self.prompt = spec.get("prompt", "Hold E to interact")
        self.current = None
        self.marker = self.points[0] if self.points else None

    def update(self, ctx, dt):
        if not self.left:
            return True
        eye = ctx.player_eye_position()
        nearest = min(self.left, key=lambda i: math.dist(eye, self.points[i]))
        p = self.points[nearest]
        self.marker = p
        in_range = math.dist(eye, p) <= self.spec.get("radius", 2.5) and ctx.player_looking_at(p, 45.0)
        if nearest != self.current:
            self.current, self.held = nearest, 0.0
        if in_range:
            self.held = self.held + dt if ctx.interact_held() else max(0.0, self.held - dt * 2.0)
            ctx.set_prompt(self.prompt, self.held / self.hold_time if self.held > 0 else None)
        else:
            self.held = 0.0
            ctx.set_prompt(None)
        if self.held >= self.hold_time:
            self.left.remove(nearest)
            self.held = 0.0
            self.current = None
            ctx.set_prompt(None)
            ctx.point_done(self.spec, p)
        return not self.left

    def status(self):
        return f"{self.text} ({len(self.points) - len(self.left)}/{len(self.points)})"

    def finish(self, ctx):
        ctx.set_prompt(None)


class Photograph(Objective):
    """Aim down sights at enemies of a group and hold steady to photograph them (dead ones count too)."""

    def __init__(self, spec):
        super().__init__(spec)
        self.count = int(spec.get("count", 1))
        self.hold = float(spec.get("hold", 0.8))
        self.taken = set()
        self.current = None
        self.held = 0.0
        self.done = 0
        self.marker = None

    def update(self, ctx, dt):
        group = self.spec["group"]
        target = ctx.photo_target(group, float(self.spec.get("angle", 3.0)), float(self.spec.get("range", 160.0)))
        if target is not None and target not in self.taken:
            if target != self.current:
                self.current, self.held = target, 0.0
            self.held += dt
            ctx.set_prompt("Hold steady - photographing", min(1.0, self.held / self.hold))
            if self.held >= self.hold:
                self.taken.add(target)
                self.current, self.held = None, 0.0
                ctx.set_prompt(None)
                ctx.photo_taken(len(self.taken), self.count)
        else:
            self.current, self.held = None, 0.0
            ctx.set_prompt("Already photographed" if target is not None else None)
        members = ctx.group_members(group)                        # [(key, (x, y, z), alive)]
        dead = sum(1 for key, _, alive in members if not alive and key not in self.taken)
        self.done = min(self.count, len(self.taken) + dead)
        left = [pos for key, pos, alive in members if alive and key not in self.taken]
        self.marker = (left[0][0], left[0][1], left[0][2] + 2.4) if left and self.spec.get("marker", True) else None
        return bool(members) and self.done >= self.count

    def status(self):
        return f"{self.text} ({self.done}/{self.count})"

    def finish(self, ctx):
        ctx.set_prompt(None)


class Download(Objective):
    """Start a download at a terminal (hold E), then stay close until it reaches 100 %."""

    def __init__(self, spec):
        super().__init__(spec)
        self.seconds = float(spec.get("seconds", 40.0))
        self.radius = float(spec.get("radius", 8.0))
        self.start_hold = float(spec.get("hold", 1.0))
        self.held = 0.0
        self.started = False
        self.progress = 0.0

    def update(self, ctx, dt):
        pos = self.spec["pos"]
        eye = ctx.player_eye_position()
        if not self.started:
            near = math.dist(eye, pos) <= self.spec.get("start_radius", 2.5) and ctx.player_looking_at(pos, 40.0)
            if near:
                self.held = self.held + dt if ctx.interact_held() else max(0.0, self.held - dt * 2)
                ctx.set_prompt(self.spec.get("prompt", "Hold E to start the download"),
                               self.held / self.start_hold if self.held > 0 else None)
                if self.held >= self.start_hold:
                    self.started = True
                    ctx.download_started(self.spec)
            else:
                self.held = 0.0
                ctx.set_prompt(None)
            return False
        px, py, pz = ctx.player_position()
        if math.hypot(px - pos[0], py - pos[1]) <= self.radius and abs(pz - (pos[2] - 1.0)) < 3.0:
            self.progress += dt
            ctx.set_prompt(f"Downloading... {self.percent}%  - stay close", self.progress / self.seconds)
        else:
            ctx.set_prompt(f"DOWNLOAD PAUSED - get back to the terminal ({self.percent}%)", self.progress / self.seconds)
        if self.progress >= self.seconds:
            ctx.set_prompt(None)
            return True
        return False

    @property
    def percent(self):
        return min(100, int(100 * self.progress / self.seconds))

    def status(self):
        return f"{self.text} ({self.percent}%)" if self.started else self.text

    def finish(self, ctx):
        ctx.set_prompt(None)


class Rescue(Objective):
    """Kill the captors before they execute the hostage. Once they notice you, a short timer starts."""

    def __init__(self, spec):
        super().__init__(spec)
        self.seconds = float(spec.get("seconds", 5.0))
        self.timer = None
        self.executed = False

    def update(self, ctx, dt):
        group, hostage = self.spec["group"], self.spec["hostage"]
        total, alive = ctx.group_total(group), ctx.group_alive(group)
        if self.timer is None and alive > 0 and ctx.group_alerted(group):
            self.timer = self.seconds
            ctx.notice(self.spec.get("warning", "THEY'RE GOING TO KILL THE HOSTAGE!"))
        if self.timer is not None and alive > 0 and not self.executed:
            self.timer -= dt
            if self.timer <= 0.0:
                self.executed = True
                ctx.execute_hostage(hostage, group)
        return total > 0 and alive == 0 and ctx.squad_alive(hostage)

    def status(self):
        if self.timer is not None and not self.executed:
            return f"{self.text} ({max(0, math.ceil(self.timer))} s!)"
        return self.text


TYPES = {"reach": ReachArea, "interact": Interact, "eliminate": EliminateGroup, "survive": Survive,
         "escort": Escort, "ride": Ride, "tag": Tag, "destroy": DestroyVehicles, "vehicles_arrive": VehiclesArrive,
         "interact_multi": InteractMulti, "photograph": Photograph, "download": Download, "rescue": Rescue}


def make_objective(spec):
    kind = spec.get("type")
    if kind not in TYPES:
        raise ValueError(f"Unknown objective type '{kind}'")
    return TYPES[kind](spec)
