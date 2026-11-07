"""Keyboard and mouse input.

Buttons are POLLED every frame (instead of using key events). This avoids a Panda3D
pitfall where holding Shift/Ctrl turns "w" into "shift-w" events and movement stops.

Mouse look: while the mouse is captured, the cursor is hidden and moved back to the
centre of the window every frame; the distance it travelled is the look delta.
"""
from __future__ import annotations

import logging

from panda3d.core import ButtonHandle, ButtonRegistry, ModifierButtons, WindowProperties

log = logging.getLogger(__name__)


class InputManager:
    def __init__(self, base, bindings, event_bindings=None):
        self._base = base
        self._bindings = {}
        # Without this, holding Shift turns "wheel_up" into "shift-wheel_up".
        if base.mouseWatcherNode is not None:
            base.mouseWatcherNode.set_modifier_buttons(ModifierButtons())
        for thrower in getattr(base, "buttonThrowers", []) or []:
            thrower.node().set_modifier_buttons(ModifierButtons())
        self._event_queue = set()
        self._scripted_queue = set()
        self.capture_enabled = True          # automated tests turn this off so they never grab your mouse
        for event, action in (event_bindings or {}).items():
            base.accept(event, self._event_queue.add, [action])
        registry = ButtonRegistry.ptr()
        for action, names in bindings.items():
            handles = []
            for name in names:
                handle = registry.find_button(name)
                if handle == ButtonHandle.none():
                    log.warning("Unknown button '%s' for action '%s'", name, action)
                else:
                    handles.append(handle)
            self._bindings[action] = handles
        self._down = {action: False for action in self._bindings}
        self._pressed = set()
        self._released = set()
        self.mouse_dx = 0.0
        self.mouse_dy = 0.0
        self.mouse_captured = False
        self._skip_mouse_frames = 0
        # Automated tests drive the game through these instead of the real keyboard.
        self.scripted_down = None          # set of action names held down, or None for real input
        self._injected_dx = 0.0
        self._injected_dy = 0.0

    # ------------------------------------------------------------------ per frame
    def update(self):
        self._pressed.clear()
        self._released.clear()
        watcher = self._base.mouseWatcherNode
        for action, handles in self._bindings.items():
            if self.scripted_down is not None:
                now = action in self.scripted_down
            else:
                now = watcher is not None and any(watcher.is_button_down(h) for h in handles)
            was = self._down[action]
            if now and not was:
                self._pressed.add(action)
            elif was and not now:
                self._released.add(action)
            self._down[action] = now
        scripted = self.scripted_down is not None
        if not scripted:
            self._pressed |= self._event_queue          # real mouse-wheel events
        self._pressed |= self._scripted_queue
        self._event_queue.clear()
        self._scripted_queue.clear()
        self._read_mouse(real=not scripted)

    def press_once(self, action):
        """Make `action` count as pressed on the next frame (used by automated tests)."""
        self._scripted_queue.add(action)

    def _read_mouse(self, real=True):
        dx = dy = 0.0
        win = self._base.win
        if real and self.mouse_captured and win is not None:
            cx, cy = win.get_x_size() // 2, win.get_y_size() // 2
            pointer = win.get_pointer(0)
            if self._skip_mouse_frames > 0:
                self._skip_mouse_frames -= 1
            elif pointer.get_in_window():
                dx = pointer.get_x() - cx
                dy = pointer.get_y() - cy
            win.move_pointer(0, cx, cy)
        self.mouse_dx = dx + self._injected_dx
        self.mouse_dy = dy + self._injected_dy
        self._injected_dx = self._injected_dy = 0.0

    # ------------------------------------------------------------------ queries
    def is_down(self, action):
        return self._down.get(action, False)

    def was_pressed(self, action):
        return action in self._pressed

    def was_released(self, action):
        return action in self._released

    def axis(self, positive, negative):
        return (1.0 if self.is_down(positive) else 0.0) - (1.0 if self.is_down(negative) else 0.0)

    def inject_mouse(self, dx, dy):
        """Add a fake mouse movement (used by automated tests)."""
        self._injected_dx += dx
        self._injected_dy += dy

    # ------------------------------------------------------------------ mouse capture
    def capture_mouse(self, capture):
        win = self._base.win
        if win is None:
            return
        if not self.capture_enabled:
            capture = False
        props = WindowProperties()
        props.set_cursor_hidden(capture)
        props.set_mouse_mode(WindowProperties.M_confined if capture else WindowProperties.M_absolute)
        win.request_properties(props)
        self.mouse_captured = capture
        self._skip_mouse_frames = 2
        if capture:
            win.move_pointer(0, win.get_x_size() // 2, win.get_y_size() // 2)
