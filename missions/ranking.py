"""Mission rank (Gold / Silver / Bronze) from the end-of-mission stats.

One point each for: finishing within par time, no retries, accuracy of 30 % or better,
staying undetected (missions with an alarm), and finding all intel (missions with intel).
Gold needs every available point but one at most; Silver needs at least half.
"""
from __future__ import annotations

DEFAULT_PAR = 1200.0
RANKS = ("BRONZE", "SILVER", "GOLD")


def score(stats, par_time=None):
    points, possible = 0, 3
    par = float(par_time or DEFAULT_PAR)
    if stats.get("time", 1e9) <= par:
        points += 1
    if stats.get("deaths", 0) == 0:
        points += 1
    if stats.get("accuracy", 0.0) >= 0.30:
        points += 1
    if stats.get("stealth") is not None:
        possible += 1
        points += 1 if stats["stealth"] else 0
    if stats.get("intel_total", 0) > 0:
        possible += 1
        points += 1 if stats.get("intel", 0) >= stats["intel_total"] else 0
    return points, possible


def rank(stats, par_time=None):
    points, possible = score(stats, par_time)
    if points >= possible - 1 and points >= 3:
        return "GOLD"
    if points * 2 >= possible:
        return "SILVER"
    return "BRONZE"


def better(a, b):
    """The better of two rank names (None counts as no rank)."""
    ia = RANKS.index(a) if a in RANKS else -1
    ib = RANKS.index(b) if b in RANKS else -1
    return a if ia >= ib else b
