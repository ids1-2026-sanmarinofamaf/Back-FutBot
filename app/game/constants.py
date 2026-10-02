"""
Global constants used by the game simulation.
"""

# Field width in meters
FIELD_WIDTH = 40.0

# Field height in meters
FIELD_HEIGHT = 20.0

# Goal width in meters
GOAL_WIDTH = 3.0

# Player collision radius in meters
PLAYER_RADIUS = 0.25

# Ball collision radius in meters
BALL_RADIUS = 0.10

# Number of simulation tics executed per second
TICS_PER_SECOND = 10

# Duration of one simulation tic in seconds
TIC_DURATION = 0.1

# Fraction of ball speed preserved after bouncing off a wall
WALL_BOUNCE_SPEED_FACTOR = 0.9

# Fraction of ball speed preserved after bouncing off a player
PLAYER_BOUNCE_SPEED_FACTOR = 0.6

# Fraction of the ball's previous velocity preserved when kicked
KICK_INERTIA_FACTOR = 0.4

# Maximum allowed ball speed in meters per second
MAX_BALL_SPEED = 40.0

# Ball friction
MIN_BALL_DECELERATION = 0.5
MAX_BALL_DECELERATION = 2.0

# Ball speeds below this value are treated as zero
BALL_STOP_THRESHOLD = 0.5

# Center position of each goal
LEFT_GOAL = (0.0, FIELD_HEIGHT / 2)
RIGHT_GOAL = (FIELD_WIDTH, FIELD_HEIGHT / 2)

# PACSS
MIN_PACSS = 20
MAX_PACSS = 100

# Physics model
MIN_MOVE_SPEED = 6.0
MAX_MOVE_SPEED = 9.5

MIN_KICK_FORCE = 20.0
MAX_KICK_FORCE = 35.0

MIN_CONTROL_RANGE = 0.4
MAX_CONTROL_RANGE = 1.2

MIN_KICK_COOLDOWN_TICS = 1
MAX_KICK_COOLDOWN_TICS = 20

COLLISION_PENALTY = 0.5