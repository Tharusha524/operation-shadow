"""Smooth paths for vehicles (boats, helicopters, tanks, drones).

A path is a list of 3D points. Positions are sampled by distance along a Catmull-Rom
spline, so vehicles move smoothly through the points instead of in straight lines.
"""
from __future__ import annotations

import math


def _catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return tuple(0.5 * ((2 * p1[i]) + (-p0[i] + p2[i]) * t + (2 * p0[i] - 5 * p1[i] + 4 * p2[i] - p3[i]) * t2
                        + (-p0[i] + 3 * p1[i] - 3 * p2[i] + p3[i]) * t3) for i in range(3))


class Path:
    def __init__(self, points, samples_per_segment=16, loop=False):
        pts = [tuple(float(v) for v in (list(p) + [0.0])[:3]) for p in points]
        if len(pts) < 2:
            raise ValueError("a path needs at least two points")
        self.loop = loop
        self.points = pts
        self._samples = []           # (distance, x, y, z)
        ext = ([pts[-1]] + pts + [pts[0], pts[1]]) if loop else ([pts[0]] + pts + [pts[-1]])
        segments = len(pts) if loop else len(pts) - 1
        dist = 0.0
        prev = None
        for s in range(segments):
            p0, p1, p2, p3 = ext[s], ext[s + 1], ext[s + 2], ext[s + 3]
            for k in range(samples_per_segment + (1 if s == segments - 1 else 0)):
                q = _catmull(p0, p1, p2, p3, k / samples_per_segment)
                if prev is not None:
                    dist += math.dist(prev, q)
                self._samples.append((dist, *q))
                prev = q
        self.length = dist

    def point_at(self, d):
        """(x, y, z) at distance d along the path (clamped, or wrapped for loops)."""
        if self.loop and self.length > 0:
            d %= self.length
        d = max(0.0, min(self.length, d))
        s = self._samples
        lo, hi = 0, len(s) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if s[mid][0] <= d:
                lo = mid
            else:
                hi = mid
        a, b = s[lo], s[hi]
        span = b[0] - a[0]
        t = 0.0 if span <= 1e-9 else (d - a[0]) / span
        return a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t

    def heading_at(self, d):
        """Panda3D heading (degrees) of the path direction at distance d."""
        a = self.point_at(d - 0.5)
        b = self.point_at(d + 0.5)
        return math.degrees(math.atan2(-(b[0] - a[0]), b[1] - a[1]))

    def closest_distance(self, pos):
        """Distance along the path of the sample closest to pos."""
        best = min(self._samples, key=lambda s: (s[1] - pos[0]) ** 2 + (s[2] - pos[1]) ** 2 + (s[3] - pos[2]) ** 2)
        return best[0]
