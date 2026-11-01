from dataclasses import dataclass

from app.game.context import CoachContext


@dataclass(frozen=True)
class CoachJob:
    """
    Represent a coach (DT) execution request for one club.

    Attributes:
        club_id: Identifier of the club whose coach must be executed.
        coach_behavior_id: Identifier of the coach behavior chosen by the club.
        context: CoachContext visible to the coach during the current tic.
    """
    club_id: int
    coach_behavior_id: int
    context: CoachContext
