"""Navigation grid for AI soldiers: walkable cells, A* path finding and cover points.

The level is sampled on a 1 m grid. A cell is walkable if a soldier (radius 0.4 m)
can stand there on the ground. Cover points are walkable cells right next to an
obstacle at least ~1 m tall (sandbags, walls, vehicles).
"""
from __future__ import annotations

import heapq
import math

SQRT2 = math.sqrt(2.0)


class NavGrid:
    def __init__(self, world, bounds, cell=1.0, agent_radius=0.3, agent_height=1.7):
        self.world = world
        self.x0, self.y0, self.x1, self.y1 = bounds
        self.cell = cell
        self.nx = int(math.ceil((self.x1 - self.x0) / cell))
        self.ny = int(math.ceil((self.y1 - self.y0) / cell))
        self.radius = agent_radius
        self.height = agent_height
        self.walkable = bytearray(self.nx * self.ny)
        self.cover_points = []          # (x, y, nx, ny) - normal points from the obstacle towards the soldier
        self.rebuild()

    # ------------------------------------------------------------------ building
    def rebuild(self, area=None):
        """(Re)compute walkability for the whole grid or only inside area=(x0, y0, x1, y1)."""
        i0, j0, i1, j1 = 0, 0, self.nx - 1, self.ny - 1
        if area is not None:
            i0, j0 = self.to_cell(area[0], area[1])
            i1, j1 = self.to_cell(area[2], area[3])
            i0, j0, i1, j1 = max(0, i0 - 1), max(0, j0 - 1), min(self.nx - 1, i1 + 1), min(self.ny - 1, j1 + 1)
        world, r, h = self.world, self.radius, self.height
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                x, y = self.cell_center(i, j)
                z = world.ground_height(x, y, r * 0.5, 0.45)
                free = -1.0 < z < 0.3 and world.is_free(x, y, r, z + 0.45, z + h)
                self.walkable[j * self.nx + i] = 1 if free else 0
        self._find_cover()

    def _find_cover(self):
        self.cover_points = []
        world = self.world
        for j in range(1, self.ny - 1):
            for i in range(1, self.nx - 1):
                if not self.walkable[j * self.nx + i]:
                    continue
                x, y = self.cell_center(i, j)
                for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if self.walkable[(j + dj) * self.nx + (i + di)]:
                        continue
                    # Blocked neighbour: is it tall enough to hide behind when crouched?
                    tall = any(not world.is_free(x + di * self.cell * k, y + dj * self.cell * k, 0.3, 0.9, 1.05)
                               for k in (0.8, 1.2, 1.6))
                    if tall:
                        self.cover_points.append((x, y, -di, -dj))
                        break

    # ------------------------------------------------------------------ helpers
    def to_cell(self, x, y):
        return int((x - self.x0) // self.cell), int((y - self.y0) // self.cell)

    def cell_center(self, i, j):
        return self.x0 + (i + 0.5) * self.cell, self.y0 + (j + 0.5) * self.cell

    def in_bounds(self, i, j):
        return 0 <= i < self.nx and 0 <= j < self.ny

    def is_walkable(self, x, y):
        i, j = self.to_cell(x, y)
        return self.in_bounds(i, j) and self.walkable[j * self.nx + i] == 1

    def nearest_walkable(self, x, y, max_radius=6):
        i, j = self.to_cell(x, y)
        if self.in_bounds(i, j) and self.walkable[j * self.nx + i]:
            return self.cell_center(i, j)
        for r in range(1, max_radius + 1):
            best = None
            for dj in range(-r, r + 1):
                for di in range(-r, r + 1):
                    if max(abs(di), abs(dj)) != r:
                        continue
                    ci, cj = i + di, j + dj
                    if self.in_bounds(ci, cj) and self.walkable[cj * self.nx + ci]:
                        d = di * di + dj * dj
                        if best is None or d < best[0]:
                            best = (d, ci, cj)
            if best:
                return self.cell_center(best[1], best[2])
        return None

    def line_walkable(self, ax, ay, bx, by):
        """True if a straight walk from a to b stays on walkable cells."""
        dist = math.hypot(bx - ax, by - ay)
        steps = max(1, int(dist / (self.cell * 0.4)))
        for s in range(steps + 1):
            t = s / steps
            if not self.is_walkable(ax + (bx - ax) * t, ay + (by - ay) * t):
                return False
        return True

    # ------------------------------------------------------------------ A*
    def find_path(self, start, goal, max_nodes=12000, weight=1.4):
        """List of (x, y) waypoints from start to goal (smoothed), or None if unreachable.

        weight > 1 makes A* "greedier": much faster on big maps, paths stay almost as short.
        """
        s = self.nearest_walkable(*start)
        g = self.nearest_walkable(*goal)
        if s is None or g is None:
            return None
        if self.line_walkable(s[0], s[1], g[0], g[1]):
            return [g]                                   # straight line is clear - no search needed
        si, sj = self.to_cell(*s)
        gi, gj = self.to_cell(*g)
        nx = self.nx
        start_id, goal_id = sj * nx + si, gj * nx + gi
        if start_id == goal_id:
            return [g]
        walk = self.walkable
        open_heap = [(0.0, start_id)]
        came = {start_id: -1}
        cost = {start_id: 0.0}
        expanded = 0
        neighbours = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                      (1, 1, SQRT2), (1, -1, SQRT2), (-1, 1, SQRT2), (-1, -1, SQRT2))
        while open_heap:
            _, cur = heapq.heappop(open_heap)
            if cur == goal_id:
                break
            expanded += 1
            if expanded > max_nodes:
                return None
            ci, cj = cur % nx, cur // nx
            base = cost[cur]
            for di, dj, c in neighbours:
                ni, nj = ci + di, cj + dj
                if not (0 <= ni < nx and 0 <= nj < self.ny):
                    continue
                nid = nj * nx + ni
                if not walk[nid]:
                    continue
                if di and dj and (not walk[cj * nx + ni] or not walk[nj * nx + ci]):
                    continue        # don't cut corners
                new_cost = base + c
                if new_cost < cost.get(nid, 1e18):
                    cost[nid] = new_cost
                    came[nid] = cur
                    h = math.hypot(gi - ni, gj - nj) * weight
                    heapq.heappush(open_heap, (new_cost + h, nid))
        if goal_id not in came:
            return None
        cells = []
        cur = goal_id
        while cur != -1:
            cells.append(self.cell_center(cur % nx, cur // nx))
            cur = came[cur]
        cells.reverse()
        return self._smooth(cells)

    def _smooth(self, points):
        if len(points) <= 2:
            return points[1:] if len(points) == 2 else points
        out = []
        anchor = points[0]
        i = 1
        while i < len(points):
            j = len(points) - 1
            while j > i and not self.line_walkable(anchor[0], anchor[1], points[j][0], points[j][1]):
                j -= 1
            out.append(points[j])
            anchor = points[j]
            i = j + 1
        return out

    # ------------------------------------------------------------------ cover
    def find_cover(self, x, y, threat, max_dist=18.0, min_dist=1.5, occupied=(), avoid_radius=1.6):
        """Best cover point near (x, y) that blocks the line of sight from `threat` (x, y, z)."""
        world = self.world
        best = None
        tx, ty, tz = threat
        for cx, cy, nx_, ny_ in self.cover_points:
            d = math.hypot(cx - x, cy - y)
            if d > max_dist or d < min_dist * 0.0:
                continue
            if any(math.hypot(cx - ox, cy - oy) < avoid_radius for ox, oy in occupied):
                continue
            # The obstacle must sit between the threat and the cover spot.
            to_threat = (tx - cx, ty - cy)
            if to_threat[0] * -nx_ + to_threat[1] * -ny_ <= 0:
                continue
            if world.line_of_sight((tx, ty, tz), (cx, cy, 0.9)):
                continue
            dist_threat = math.hypot(tx - cx, ty - cy)
            score = d + max(0.0, 8.0 - dist_threat) * 2.0
            if best is None or score < best[0]:
                best = (score, cx, cy)
        return (best[1], best[2]) if best else None
