"""
Basic data types exposed by the Behavior API.
"""
from enum import Enum


# Data type representing a position on the field: (x,y)
Position = tuple[float, float]

# Data type representing a direction with a unit vector: (x,y)
Direction = tuple[float, float]

# Data type representing a velocity on the field: (x,y)
Velocity = tuple[float, float]

# Data type representing a player by its id and current position
PlayerState = tuple[int, Position]

# Data type representing a ball by its current position and velocity
BallState = tuple[Position, Velocity]

# Data type representing a coach assignment of a behavior to a player
Assignment = tuple[int, str]  # (player_id, behavior_name)


# Enum representing the periods of a match
class Period(Enum):
    FIRST_QUARTER = 1
    SECOND_QUARTER = 2
    THIRD_QUARTER = 3
    FOURTH_QUARTER = 4
    

# Enum representing the field's sides
class Side(Enum):
    LEFT = "left"
    RIGHT = "right"

# Enum representing the event that triggered a coach execution
class CoachTrigger(Enum):
    GOAL_FOR = "GOAL_FOR"
    GOAL_AGAINST = "GOAL_AGAINST"
    PERIOD_START = "PERIOD_START"
