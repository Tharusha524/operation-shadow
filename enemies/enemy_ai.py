"""Finite-state-machine AI for soldiers (enemies and squad mates).

States
  IDLE         stand at a post, look around
  PATROL       walk a route of waypoints
  INVESTIGATE  go to a heard noise / last seen position and search
  CHASE        run to where the target was last seen
  ATTACK       face, strafe and shoot in bursts
  TAKE_COVER   run to cover, hide, reload, peek out and shoot
  DEAD
Squad-only
  FOLLOW       stay in formation near the player
  HOLD         stay at a position given by the mission (still shoots)

Perception: a view cone + line-of-sight ray, an "awareness" meter that fills faster
when the target is close, hearing gunshots/explosions, and alerts shouted by allies.
"""
from __future__ import annotations

import math

from enemies.soldier import angle_diff, heading_to
from player.movement import MotorInput

IDLE, PATROL, INVESTIGATE, CHASE, ATTACK, TAKE_COVER, DEAD = (
    "IDLE", "PATROL", "INVESTIGATE", "CHASE", "ATTACK", "TAKE_COVER", "DEAD")
FOLLOW, HOLD, ESCORT = "FOLLOW", "HOLD", "ESCORT"
CALM_STATES = (IDLE, PATROL, INVESTIGATE, FOLLOW, HOLD)
COMBAT_STATES = (ATTACK, TAKE_COVER, CHASE)

THINK_INTERVAL = 0.15
TURN_RATE = 320.0
FORMATION = ((-2.6, -2.2), (2.6, -2.4), (0.0, -4.4), (-4.5, -4.0))


class SoldierAI:
    def __init__(self, soldier, profile, patrol=None, post=None):
        self.s = soldier
        self.p = profile
        self.rng = soldier.manager.rng
        self.is_squad = soldier.team == "friendly"
        self.patrol = [tuple(p) for p in (patrol or [])]
        self.patrol_index = 0
        self.post = post
        self.state = FOLLOW if self.is_squad else (PATROL if self.patrol else IDLE)
        self.state_time = 0.0
        self.target = None
        self.target_visible = False
        self.last_known = None
        self.lost_time = 0.0
        self.awareness = 0.0
        self.think_timer = self.rng.uniform(0.0, THINK_INTERVAL)
        self.path = []
        self.path_goal = None
        self.repath_timer = 0.0
        self.burst_left = 0
        self.burst_timer = 0.0
        self.reaction_timer = 0.0
        self.cover = None
        self.cover_phase = None
        self.cover_timer = 0.0
        self.cover_cycles = 0
        self.investigate_pos = None
        self.strafe = 0
        self.strafe_timer = 0.0
        self.anchor = None               # (x, y, heading) - HOLD position
        self.damage_recent = 0.0
        self.grenade_timer = self.rng.uniform(6.0, 12.0)
        self.desired_facing = soldier.facing
        self.formation_index = 0
        self.leader = None               # follow this soldier instead of the player (e.g. Marek helping Kell)
        self.escort = None               # wounded soldier walking a route: {"route", "i", "danger", "wait_call"}
        self._stuck_timer = 0.0
        self._stuck_ref = (soldier.motor.x, soldier.motor.y)
        self._wait = 0.0
        self.stunned = 0.0               # seconds left blinded by a flashbang

    # ================================================================== public hooks
    def set_state(self, state):
        if state == self.state:
            return
        self.state = state
        self.state_time = 0.0
        self.path, self.path_goal = [], None
        if state != TAKE_COVER:
            self.cover, self.cover_phase = None, None
            self.s.manager.release_cover(self.s)
        if state in (ATTACK, TAKE_COVER):
            self.burst_left = 0
            self.burst_timer = self.rng.uniform(0.1, 0.4)

    def command_follow(self):
        self.anchor = None
        if self.state not in COMBAT_STATES:
            self.set_state(FOLLOW)

    def command_escort(self, route):
        """Wounded soldier: walk the route (waits for the player, ducks when enemies are close, never shoots)."""
        route = [tuple(p[:2]) for p in route]
        mx, my = self.s.motor.x, self.s.motor.y
        # Resume from the route point nearest to where we are now.
        start = min(range(len(route)), key=lambda i: math.hypot(route[i][0] - mx, route[i][1] - my))
        self.escort = {"route": route, "i": start, "danger": 0.0, "wait_call": 0.0}
        self.anchor = None
        self.set_state(ESCORT)

    def command_hold(self, x, y, heading=None):
        self.anchor = (x, y, heading if heading is not None else self.s.facing)
        if self.state not in COMBAT_STATES:
            self.set_state(HOLD)

    def on_damaged(self, source, amount):
        if source is None or getattr(source, "team", None) == self.s.team:
            return
        if self.escort is not None:          # the wounded don't fight back - they get down
            self.escort["danger"] = 3.0
            return
        self.damage_recent += amount
        self.target = source
        self.last_known = source.position
        self.awareness = 1.0
        if self.state in CALM_STATES or self.state == CHASE:
            self._engage(react=0.25)
        elif self.state == ATTACK and self.damage_recent > 25:
            self._try_cover()

    def hear(self, position, source):
        if self.is_squad or self.state not in CALM_STATES:
            return
        if self.anchor is not None:          # guards stay at their post and just look towards the noise
            self.desired_facing = heading_to(position[0] - self.s.motor.x, position[1] - self.s.motor.y)
            self.awareness = max(self.awareness, 0.5)
            return
        jitter = 3.0
        self.investigate_pos = (position[0] + self.rng.uniform(-jitter, jitter),
                                position[1] + self.rng.uniform(-jitter, jitter))
        self.awareness = max(self.awareness, 0.5)
        if source is not None:
            self.target = source
            self.last_known = source.position
        self.set_state(INVESTIGATE)

    def alert(self, target, position):
        """An ally shouted that they saw `target` at `position`."""
        if self.state not in CALM_STATES or self.is_squad:
            return
        self.target = target
        self.last_known = position
        self.awareness = max(self.awareness, 0.85)
        if self.anchor is not None:          # hold the position, but face the threat
            self.desired_facing = heading_to(position[0] - self.s.motor.x, position[1] - self.s.motor.y)
            return
        self.set_state(CHASE)

    def stun(self, seconds):
        """Flashbang: blind for a few seconds; afterwards they know something is wrong."""
        if self.state == DEAD:
            return
        self.stunned = max(self.stunned, seconds)
        self.awareness = max(self.awareness, 0.7)

    # ================================================================== main update
    def update(self, dt):
        s = self.s
        self.state_time += dt
        self.damage_recent = max(0.0, self.damage_recent - 8.0 * dt)
        self.grenade_timer -= dt
        self.repath_timer -= dt
        self.think_timer -= dt
        if self.think_timer <= 0.0:
            self.think_timer = THINK_INTERVAL
            self._perceive(THINK_INTERVAL)
        s.move_input = MotorInput(yaw=s.facing, crouch=s.crouch)
        if self.stunned > 0.0 and self.state != DEAD:
            # Blinded and deafened: stagger, don't see, don't shoot.
            self.stunned -= dt
            self.target_visible = False
            s.aiming = False
            self.burst_left = 0
            self.desired_facing = s.facing + math.sin(self.state_time * 7.0) * 30.0
            self._turn(dt)
            return
        if s.mount is not None and self.state != DEAD:
            self._mounted(dt)
            self._turn(dt)
            return
        handler = getattr(self, f"_state_{self.state.lower()}")
        handler(dt)
        self._turn(dt)
        self._check_stuck(dt)

    # ================================================================== perception
    def _perceive(self, dt):
        s = self.s
        mgr = s.manager
        best = None
        ex, ey, ez = s.eye_position()
        in_combat = self.state in COMBAT_STATES
        half_fov = (200.0 if in_combat else self.p["fov"]) / 2.0
        candidates = []
        for t in mgr.hostiles(s.team):
            if not t.alive:
                continue
            tx, ty, tz = t.center()
            d = math.hypot(tx - ex, ty - ey)
            if d > self.p["vision_range"] * mgr.vision_scale(s, t):
                continue
            behind = abs(angle_diff(heading_to(tx - ex, ty - ey), s.facing)) > half_fov
            if behind:
                # Outside the view cone you can only "sense" someone very close who isn't sneaking.
                tm = getattr(t, "motor", None)
                sneaking = tm is not None and (tm.crouching or tm.horizontal_speed < 0.5)
                if d > 4.0 or (sneaking and not in_combat):
                    continue
            candidates.append((d, t))
        # Line-of-sight rays are the expensive part: test the closest few only.
        candidates.sort(key=lambda c: c[0])
        for d, t in candidates[:4]:
            tx, ty, tz = t.center()
            hx, hy, hz = t.eye_position()
            if mgr.clear_view((ex, ey, ez), (hx, hy, hz)) or mgr.clear_view((ex, ey, ez), (tx, ty, tz)):
                best = (t, d)
                break
        if best is not None:
            t, d = best
            self.target = t
            self.target_visible = True
            self.last_known = t.position
            self.lost_time = 0.0
            rate = (1.0 / self.p["reaction_time"]) * (0.35 + 8.0 / max(d, 2.0))
            if getattr(t, "motor", None) is not None and t.motor.crouching:
                rate *= 0.6
            if in_combat:
                rate *= 4.0
            self.awareness = min(1.0, self.awareness + rate * dt)
            if self.awareness >= 1.0 and self.state in CALM_STATES + (CHASE,) and self.escort is None \
                    and s.profile_name != "wounded":
                self._engage()
        else:
            self.target_visible = False
            self.lost_time += dt
            if not in_combat:
                self.awareness = max(0.0, self.awareness - 0.15 * dt)

    def _engage(self, react=None):
        s = self.s
        if self.target is None:
            return
        s.manager.callout(s, "contact")
        s.manager.alert_allies(s, self.target, self.last_known)
        self.reaction_timer = react if react is not None else self.p["reaction_time"] * self.rng.uniform(0.8, 1.2)
        if not self.is_squad and self.rng.random() < (1.0 - self.p["aggression"]) * 0.7 and self._try_cover():
            return
        self.set_state(ATTACK)

    def _try_cover(self):
        s = self.s
        if self.target is None or self.anchor is not None:     # soldiers holding a position never leave it
            return False
        threat = self.target.eye_position() if self.target.alive else (*self.last_known[:2], 1.6)
        spot = s.manager.find_cover(s, threat)
        if spot is None:
            return False
        self.set_state(TAKE_COVER)
        self.cover = spot
        self.cover_phase = "moving"
        self.cover_cycles = 0
        s.manager.claim_cover(s, spot)
        return True

    # ================================================================== states
    def _state_idle(self, dt):
        self._stop()
        base = self.post[2] if self.post else self.s.facing
        self.desired_facing = base + 35.0 * math.sin(self.state_time * 0.35 + id(self) % 7)
        if self.patrol and self.state_time > 4.0:
            self.set_state(PATROL)
        elif self.post and math.hypot(self.s.motor.x - self.post[0], self.s.motor.y - self.post[1]) > 2.0:
            self._move_to(self.post[:2], run=False)

    def _state_patrol(self, dt):
        if not self.patrol:
            self.set_state(IDLE)
            return
        if self._wait > 0.0:
            self._wait -= dt
            self._stop()
            return
        goal = self.patrol[self.patrol_index]
        if self._move_to(goal, run=False):
            self.patrol_index = (self.patrol_index + 1) % len(self.patrol)
            self._wait = self.rng.uniform(1.5, 3.5)

    def _state_investigate(self, dt):
        if self.investigate_pos is None or self.state_time > 25.0:
            self._return_to_duty()
            return
        if self._wait > 0.0:
            self._wait -= dt
            self._stop()
            self.desired_facing += 70.0 * dt
            if self._wait <= 0.0:
                self.investigate_pos = None
            return
        if self._move_to(self.investigate_pos, run=self.awareness > 0.7):
            self._wait = self.rng.uniform(3.0, 5.0)

    def _state_chase(self, dt):
        if self.target_visible and self.awareness >= 1.0:
            self.set_state(ATTACK)
            return
        if self.last_known is None or self.state_time > 20.0:
            self._return_to_duty()
            return
        if self._move_to(self.last_known[:2], run=True):
            self.investigate_pos = self.last_known[:2]
            self.set_state(INVESTIGATE)
            self._wait = 4.0

    def _state_escort(self, dt):
        s = self.s
        e = self.escort
        if e is None:
            self.set_state(FOLLOW)
            return
        s.aiming = False
        mgr = s.manager
        route = e["route"]
        e["wait_call"] = max(0.0, e["wait_call"] - dt)
        player = mgr.player
        px, py = (player.position[0], player.position[1]) if player is not None else (s.motor.x, s.motor.y)
        if self.target_visible and self.target is not None and self.target.alive and \
                math.hypot(self.target.position[0] - s.motor.x, self.target.position[1] - s.motor.y) < 22.0:
            e["danger"] = 2.5
        else:
            e["danger"] = max(0.0, e["danger"] - dt)
        if e["i"] >= len(route):                         # destination reached
            s.crouch = False
            self._stop()
            self.desired_facing = heading_to(px - s.motor.x, py - s.motor.y)
            return
        if e["danger"] > 0.0:
            s.crouch = True
            self._stop()
            if e["wait_call"] <= 0.0:
                e["wait_call"] = 10.0
                mgr.callout(s, "pinned")
            return
        if math.hypot(px - s.motor.x, py - s.motor.y) > 14.0:
            s.crouch = False
            self._stop()
            self.desired_facing = heading_to(px - s.motor.x, py - s.motor.y)
            if e["wait_call"] <= 0.0:
                e["wait_call"] = 12.0
                mgr.callout(s, "wait")
            return
        s.crouch = False
        if self._move_to(route[e["i"]], run=False, reach=1.3):
            e["i"] += 1

    def _leader(self):
        return self.leader if self.leader is not None and self.leader.alive else self.s.manager.player

    def _state_follow(self, dt):
        s = self.s
        player = self._leader()
        if player is None:
            self._stop()
            return
        px, py, _ = player.position
        if hasattr(player, "camera"):
            yaw = math.radians(player.camera.look.yaw)
        else:
            yaw = math.radians(getattr(player, "facing", 0.0))
        if player.position[2] > 2.0 and math.hypot(px - s.motor.x, py - s.motor.y) < 40.0:
            # Leader is up on a roof/tower we can't reach: stay put and keep watch instead of
            # trying to stand inside the building underneath them.
            self._stop()
            return
        ox, oy = FORMATION[self.formation_index % len(FORMATION)]
        gx = px + ox * math.cos(yaw) - oy * math.sin(yaw)
        gy = py + ox * math.sin(yaw) + oy * math.cos(yaw)
        d = math.hypot(gx - s.motor.x, gy - s.motor.y)
        if d > 2.0:
            self._move_to((gx, gy), run=d > 7.0)
        else:
            self._stop()
            self.desired_facing = math.degrees(yaw)
        s.crouch = player.motor.crouching if hasattr(player, "camera") else False

    def _state_hold(self, dt):
        if self.anchor is None:
            self.set_state(FOLLOW if self.is_squad else IDLE)
            return
        if self.target_visible and self.awareness >= 1.0 and self.target is not None and self.target.alive:
            self.set_state(ATTACK)
            return
        x, y, h = self.anchor
        if math.hypot(x - self.s.motor.x, y - self.s.motor.y) > 0.4:
            self._move_to((x, y), run=True, reach=0.3)
        else:
            self._stop()
            self.desired_facing = h

    def _state_attack(self, dt):
        s = self.s
        if not self._validate_target():
            return
        tx, ty, tz = self.target.center()
        d = math.hypot(tx - s.motor.x, ty - s.motor.y)
        self._face_target()
        s.aiming = True
        if self.target_visible:
            self._fire_logic(dt, d)
            if self.anchor is not None:
                self._hold_anchor()
            elif self.is_squad and self._too_far_from_player(14.0):
                # Fighting retreat: keep shooting while moving back towards the player (or leader).
                px, py, _ = self._leader().position
                self._move_to((px, py), run=False, reach=6.0, keep_facing=True)
            else:
                self._combat_move(dt, d)
            if not self.is_squad and (self.damage_recent > 30 or
                                      self.state_time > self.rng.uniform(5, 9) * (0.5 + self.p["aggression"])):
                self.damage_recent = 0.0
                if self._try_cover():
                    return
                self.state_time = 0.0
            if s.weapon.reloading and not self.is_squad and self.rng.random() < 0.05:
                s.manager.callout(s, "reload")
        else:
            if self.anchor is not None:
                self._hold_anchor()            # e.g. step up onto the firing step to see again
            else:
                self._stop()
            s.crouch = False
            self._maybe_grenade()
            if self.lost_time > 1.6:
                if self.anchor is not None:
                    self.set_state(HOLD)
                elif self.is_squad:
                    self.set_state(FOLLOW)
                else:
                    self.set_state(CHASE)

    def _state_take_cover(self, dt):
        s = self.s
        if not self._validate_target():
            return
        if self.cover is None:
            self.set_state(ATTACK)
            return
        if self.cover_phase == "moving":
            s.aiming = False
            s.crouch = False
            if self._move_to(self.cover, run=True, reach=0.5):
                self.cover_phase = "hiding"
                self.cover_timer = self.rng.uniform(1.0, 2.4)
                if s.weapon.mag < s.weapon.stats.magazine * 0.6:
                    s.weapon.start_reload()
            elif self.state_time > 10.0:
                self.set_state(ATTACK)
            return
        self._stop()
        self._face_target()
        if self.cover_phase == "hiding":
            s.crouch = True
            s.aiming = False
            self.cover_timer -= dt
            close = self.target_visible and math.dist(self.target.position[:2], self.cover) < 5.0
            if close:
                self.set_state(ATTACK)
                return
            if self.cover_timer <= 0.0 and not s.weapon.reloading:
                self.cover_phase = "peeking"
                self.cover_timer = self.rng.uniform(1.6, 3.2)
                self.burst_timer = 0.15
            self._maybe_grenade()
        elif self.cover_phase == "peeking":
            s.crouch = False
            s.aiming = True
            if self.target_visible:
                self._fire_logic(dt, math.dist(self.target.position[:2], self.cover))
            self.cover_timer -= dt
            if self.cover_timer <= 0.0:
                self.cover_cycles += 1
                compromised = self.s.manager.world.line_of_sight(self.target.eye_position(),
                                                                 (self.cover[0], self.cover[1], 0.9))
                if compromised or self.cover_cycles >= 3:
                    if not self._try_cover():
                        self.set_state(ATTACK)
                    return
                self.cover_phase = "hiding"
                self.cover_timer = self.rng.uniform(0.8, 2.0)

    def _state_dead(self, dt):
        self._stop()

    def _mounted(self, dt):
        """Riding a boat or helicopter: no walking, just look around and shoot from the seat."""
        s = self.s
        t = self.target
        if self.target_visible and self.awareness >= 1.0 and t is not None and t.alive:
            tx, ty, _ = t.center()
            self._face_target()
            s.aiming = True
            s.crouch = False
            self._fire_logic(dt, math.hypot(tx - s.motor.x, ty - s.motor.y))
        else:
            s.aiming = False
            s.crouch = True
            if self.target is not None and not self.target.alive:
                self.target = None

    # ================================================================== combat helpers
    def _validate_target(self):
        if self.target is not None and self.target.alive:
            return True
        # Pick another visible hostile or calm down.
        self.target = None
        self.target_visible = False
        self.s.aiming = False
        self.s.crouch = False
        if self.is_squad:
            self.set_state(HOLD if self.anchor else FOLLOW)
            mx, my = self.s.motor.x, self.s.motor.y
            others = [h for h in self.s.manager.hostiles(self.s.team)
                      if math.hypot(h.position[0] - mx, h.position[1] - my) < 80.0]
            self.s.manager.callout(self.s, "kill" if others else "clear")
        else:
            self.awareness = 0.6
            self._return_to_duty()
        return False

    def _face_target(self):
        s = self.s
        tx, ty, tz = self.target.center() if self.target_visible else (*self.last_known[:2], 1.2)
        ex, ey, ez = s.eye_position()
        self.desired_facing = heading_to(tx - ex, ty - ey)
        s.aim_pitch = math.degrees(math.atan2(tz - ez, max(0.5, math.hypot(tx - ex, ty - ey))))

    def _fire_logic(self, dt, distance):
        s = self.s
        if self.reaction_timer > 0.0:
            self.reaction_timer -= dt
            return
        if s.weapon.reloading:
            return
        if abs(angle_diff(self.desired_facing, s.facing)) > 14.0:
            return
        if self.burst_left <= 0:
            self.burst_timer -= dt
            if self.burst_timer > 0.0:
                return
            lo, hi = self.p["burst"]
            self.burst_left = self.rng.randint(lo, hi)
        t = self.target
        aim = list(t.center())
        if self.rng.random() < 0.12:
            aim = list(t.eye_position())
        tm = getattr(t, "motor", None)
        target_speed = tm.horizontal_speed if tm is not None else 0.0
        spread = self.p["accuracy_spread"] * s.manager.accuracy_scale(s)
        spread *= (1.0 + target_speed / 6.0) * (1.4 if s.motor.horizontal_speed > 0.5 else 1.0)
        spread *= 0.75 if s.crouch else 1.0
        spread *= 1.0 + max(0.0, distance - 30.0) / 60.0
        if s.shoot_at(aim, spread):
            self.burst_left -= 1
            if self.burst_left <= 0:
                lo, hi = self.p["burst_pause"]
                self.burst_timer = self.rng.uniform(lo, hi)

    def _combat_move(self, dt, distance):
        s = self.s
        if distance > 38.0:
            s.crouch = False
            self._move_to(self.target.position[:2], run=False, keep_facing=True)
            return
        self.strafe_timer -= dt
        if self.strafe_timer <= 0.0:
            self.strafe_timer = self.rng.uniform(1.2, 3.0)
            roll = self.rng.random()
            self.strafe = 0 if roll < 0.4 else (1 if roll < 0.7 else -1)
            s.crouch = self.strafe == 0 and self.rng.random() < 0.6
        if self.strafe == 0:
            self._stop()
            return
        side = math.radians(s.facing - 90.0 * self.strafe)
        dx, dy = -math.sin(side), math.cos(side)
        nx_, ny_ = s.motor.x + dx * 1.5, s.motor.y + dy * 1.5
        if not s.manager.nav.line_walkable(s.motor.x, s.motor.y, nx_, ny_):
            self.strafe = -self.strafe
            self._stop()
            return
        s.crouch = False
        s.move_input = MotorInput(forward=1.0, yaw=heading_to(dx, dy), speed_scale=0.8)

    def _hold_anchor(self):
        x, y, _ = self.anchor
        if math.hypot(x - self.s.motor.x, y - self.s.motor.y) > 0.5:
            self._move_to((x, y), run=True, reach=0.3, keep_facing=True)
        else:
            self._stop()

    def _too_far_from_player(self, limit):
        player = self._leader()
        if player is None:
            return False
        px, py, _ = player.position
        return math.hypot(px - self.s.motor.x, py - self.s.motor.y) > limit

    def _maybe_grenade(self):
        s = self.s
        if self.is_squad or self.grenade_timer > 0.0 or self.last_known is None:
            return
        self.grenade_timer = self.rng.uniform(8.0, 14.0)
        if self.target_visible and self.rng.random() > 0.3:
            return
        d = math.hypot(self.last_known[0] - s.motor.x, self.last_known[1] - s.motor.y)
        if 7.0 < d < 26.0 and self.rng.random() < self.p["grenade_chance"]:
            s.manager.throw_grenade(s, self.last_known)

    def _return_to_duty(self):
        self.s.crouch = False
        self.s.aiming = False
        if self.escort is not None:
            self.set_state(ESCORT)
        elif self.anchor is not None:
            self.set_state(HOLD)
        elif self.is_squad:
            self.set_state(FOLLOW)
        elif self.patrol:
            self.set_state(PATROL)
        else:
            self.set_state(IDLE)

    # ================================================================== movement helpers
    def _stop(self):
        self.s.move_input = MotorInput(yaw=self.s.facing, crouch=self.s.crouch)

    def _move_to(self, goal, run=False, reach=0.9, keep_facing=False):
        """Follow a path towards goal. Returns True when arrived."""
        s = self.s
        x, y = s.motor.x, s.motor.y
        if math.hypot(goal[0] - x, goal[1] - y) <= reach:
            self._stop()
            self.path, self.path_goal = [], None
            return True
        if self.path_goal is None or math.hypot(goal[0] - self.path_goal[0], goal[1] - self.path_goal[1]) > 1.5 \
                or (not self.path and self.repath_timer <= 0.0):
            path = s.manager.request_path(s, (x, y), goal)
            if path is False:              # path-finding budget used up this frame - try next frame
                self._stop()
                return False
            self.path = list(path) if path else []
            self.path_goal = goal
            self.repath_timer = 2.0
            if not self.path:
                return self._step_straight(goal, run, reach, keep_facing)
        while self.path and math.hypot(self.path[0][0] - x, self.path[0][1] - y) < 0.6:
            self.path.pop(0)
        if not self.path:
            self.path_goal = None
            return self._step_straight(goal, run, reach, keep_facing)
        nx_, ny_ = self.path[0]
        heading = heading_to(nx_ - x, ny_ - y)
        s.move_input = MotorInput(forward=1.0, yaw=heading, sprint=run and not s.crouch, crouch=s.crouch)
        if not keep_facing:
            self.desired_facing = heading
            s.aiming = False
        return False

    def _step_straight(self, goal, run, reach, keep_facing):
        """Last metres without a path (e.g. up onto a trench's firing step): walk straight at the goal."""
        s = self.s
        d = math.hypot(goal[0] - s.motor.x, goal[1] - s.motor.y)
        if d <= reach or d > 3.0:
            self._stop()
            return d <= reach + 0.6
        heading = heading_to(goal[0] - s.motor.x, goal[1] - s.motor.y)
        s.move_input = MotorInput(forward=1.0 if d > 0.6 else 0.5, yaw=heading, sprint=False, crouch=s.crouch)
        if not keep_facing:
            self.desired_facing = heading
            s.aiming = False
        return False

    def _turn(self, dt):
        s = self.s
        diff = angle_diff(self.desired_facing, s.facing)
        step = TURN_RATE * dt
        s.facing = self.desired_facing if abs(diff) <= step else s.facing + math.copysign(step, diff)
        s.facing = (s.facing + 180.0) % 360.0 - 180.0

    def _check_stuck(self, dt):
        s = self.s
        wants_move = abs(s.move_input.forward) > 0.1
        if not wants_move:
            self._stuck_timer = 0.0
            self._stuck_ref = (s.motor.x, s.motor.y)
            return
        self._stuck_timer += dt
        if self._stuck_timer > 1.2:
            moved = math.hypot(s.motor.x - self._stuck_ref[0], s.motor.y - self._stuck_ref[1])
            if moved < 0.35:
                self.path_goal = None        # force a new path
                if self.state == TAKE_COVER and self.cover_phase == "moving":
                    self.set_state(ATTACK)
            self._stuck_timer = 0.0
            self._stuck_ref = (s.motor.x, s.motor.y)
