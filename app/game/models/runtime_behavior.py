"""
Runtime representation of a behavior with an identifier and executable play() function.
"""

from dataclasses import dataclass
from typing import Callable

from app.game.models.actions import MoveAction, KickAction, WaitAction

from app.game.types import Assignment

@dataclass(frozen=True)
class RuntimeBehavior:
    id: int
    play: Callable[[], MoveAction | KickAction | WaitAction]



@dataclass(frozen=True)
class RuntimeCoachBehavior:
    id: int
    coach: Callable[[], list[Assignment]]
