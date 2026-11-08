from dataclasses import dataclass

from app.game.context import BehaviorContext


@dataclass(frozen=True)
class BehaviorJob:
    """
    Represent a behavior execution request for one player.

    Attributes:
        player_id: Identifier of the player whose behavior must be executed.
        behavior_id: Identifier of the behavior assigned to the player.
        context: BehaviorContext visible to the behavior during the current tic.
    """
    player_id: int
    behavior_id: int
    context: BehaviorContext