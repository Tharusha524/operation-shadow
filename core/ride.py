"""Riding a vehicle (boat insertion, helicopter extraction).

The player and squad members are "mounted": each frame their bodies are placed on a seat of
the vehicle. The player can still look around and shoot; squad members shoot from their seats.
"""
from __future__ import annotations

import math


def seat_world(vehicle, offset):
    """Local seat offset (x right, y forward, z up) -> world position, following the vehicle's heading."""
    h = math.radians(vehicle.heading)
    ox, oy, oz = offset
    c, s = math.cos(h), math.sin(h)
    x = vehicle.pos[0] + ox * c - oy * s
    y = vehicle.pos[1] + ox * s + oy * c
    return x, y, vehicle.pos[2] + oz


class Ride:
    def __init__(self, game, vehicle, seat=(0.0, 1.6, -0.2), squad_seats=None, drive=False):
        self.game = game
        self.vehicle = vehicle
        self.drive = drive                  # the player is the driver (W/S/A/D)
        self.seat = tuple(seat)
        self.passengers = []
        game.player.mount = lambda: seat_world(self.vehicle, self.seat)
        for sid, off in (squad_seats or {}).items():
            s = game.squad.get(sid)
            if s is None:
                continue
            s.mount = (lambda off=tuple(off): seat_world(self.vehicle, off))
            s.ai.anchor = None
            s.ai.set_state("FOLLOW")
            self.passengers.append(s)

    @property
    def finished(self):
        v = self.vehicle
        return (v.finished and not self.drive) or not v.alive

    def end(self, player_pos=None, heading=None, squad_positions=None):
        """Get off. Optionally place the player and squad members on land."""
        g = self.game
        g.player.mount = None
        if player_pos is not None:
            p = player_pos
            g.player.teleport(p[0], p[1], p[2] if len(p) > 2 else 0.0,
                              heading if heading is not None else g.player.camera.look.yaw)
        for s in self.passengers:
            s.mount = None
        for sid, pos in (squad_positions or {}).items():
            s = g.squad.get(sid)
            if s is not None:
                s.motor.teleport(pos[0], pos[1], pos[2] if len(pos) > 2 else 0.0)
                s.ai.command_follow()
        self.passengers = []
