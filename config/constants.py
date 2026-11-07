"""Fixed game constants.

These are tuning numbers that the player never changes in-game.
Options the player CAN change (sensitivity, volume, graphics...) live in config/settings.py.

Units: metres, seconds, degrees.  Panda3D axes: X = right, Y = forward, Z = up.
"""

GAME_TITLE = "Operation Shadow"
GAME_VERSION = "0.2.0-phase2"

# --- Frame timing -------------------------------------------------------------
# Never simulate more than 50 ms in one frame. After a hitch (e.g. window drag)
# this prevents the player from teleporting through walls.
MAX_FRAME_DT = 1.0 / 20.0

# --- World physics ------------------------------------------------------------
GRAVITY = 20.0
MAX_FALL_SPEED = 40.0
KILL_Z = -50.0                  # falling below this height respawns the player

# --- Player body --------------------------------------------------------------
PLAYER_RADIUS = 0.35
PLAYER_STAND_HEIGHT = 1.80
PLAYER_CROUCH_HEIGHT = 1.15
PLAYER_EYE_OFFSET = 0.12        # eyes are this far below the top of the head
STEP_HEIGHT = 0.45              # obstacles lower than this are stepped onto (stairs, kerbs)
AIR_STEP_HEIGHT = 0.20          # small ledge-grab allowance while airborne
GROUND_SNAP_DISTANCE = 0.35     # stay glued to the ground when walking down stairs
GROUND_SUPPORT_FACTOR = 0.85    # fraction of the radius that must be over a ledge to stand on it

# --- Player movement ----------------------------------------------------------
WALK_SPEED = 4.6
SPRINT_SPEED = 7.4
CROUCH_SPEED = 2.3
BACKWARD_SPEED_FACTOR = 0.85
GROUND_ACCELERATION = 45.0
GROUND_DECELERATION = 35.0
AIR_ACCELERATION = 9.0
JUMP_SPEED = 6.6                # gives a jump height of about 1.1 m
COYOTE_TIME = 0.10              # you can still jump this long after walking off a ledge
JUMP_BUFFER_TIME = 0.12         # a jump pressed this long before landing still counts
CROUCH_TRANSITION_SPEED = 4.5   # metres of body height per second
SPRINT_MIN_FORWARD = 0.3        # must be pressing forward to sprint

WALK_STRIDE = 1.75              # metres between footsteps
SPRINT_STRIDE = 2.4
CROUCH_STRIDE = 1.2

# --- Camera -------------------------------------------------------------------
NEAR_CLIP = 0.05
PITCH_LIMIT = 88.0
MOUSE_DEGREES_PER_PIXEL = 0.06  # multiplied by the sensitivity setting
SPRINT_FOV_BONUS = 6.0
FOV_LERP_RATE = 8.0
EYE_SMOOTHING_RATE = 14.0       # smooths the camera when stepping up stairs
HEAD_BOB_VERTICAL = 0.032
HEAD_BOB_HORIZONTAL = 0.018
STRAFE_ROLL_DEGREES = 1.0
LANDING_DIP_STIFFNESS = 120.0

# --- Rendering ----------------------------------------------------------------
MAIN_CAMERA_MASK_BIT = 0
SHADOW_CAMERA_MASK_BIT = 1
SUN_SHADOW_DISTANCE = 120.0     # distance from the player to the shadow camera
CHUNK_SIZE = 40.0               # static geometry is grouped in chunks this big (for culling)

# --- Input --------------------------------------------------------------------
# Action name -> list of Panda3D button names. Any of the listed buttons triggers the action.
DEFAULT_KEY_BINDINGS = {
    "move_forward": ["w", "arrow_up"],
    "move_backward": ["s", "arrow_down"],
    "move_left": ["a", "arrow_left"],
    "move_right": ["d", "arrow_right"],
    "sprint": ["shift", "lshift", "rshift"],
    "jump": ["space"],
    "crouch": ["control", "lcontrol", "rcontrol", "c"],
    "pause": ["escape"],
    "toggle_debug": ["f3"],
    "fire": ["mouse1"],
    "aim": ["mouse3"],
    "reload": ["r"],
    "weapon_1": ["1"],
    "weapon_2": ["2"],
    "weapon_3": ["3"],
    "weapon_4": ["4"],
    "weapon_5": ["5"],
    "drone_up": ["space"],
    "drone_down": ["control", "lcontrol", "c"],
    "swap_weapon": ["q"],
    "grenade": ["g"],
    "grenade_type": ["t"],
    "interact": ["e"],
    "takedown": ["v"],
    "nvg": ["n"],
    "skip": ["space", "enter"],
}

# Actions triggered by one-shot events instead of held buttons (mouse wheel).
EVENT_BINDINGS = {
    "wheel_up": "prev_weapon",
    "wheel_down": "next_weapon",
}

# --- Player combat ------------------------------------------------------------
PLAYER_MAX_HEALTH = 100.0
PLAYER_REGEN_DELAY = 4.5
PLAYER_REGEN_RATE = 30.0
