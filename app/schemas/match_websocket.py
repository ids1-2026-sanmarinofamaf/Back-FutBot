from pydantic import BaseModel
from typing import Literal


class MatchPlayerState(BaseModel):
    player_id: int
    x: float
    y: float
    is_on_field: bool
    team: str


class BallState(BaseModel):
    x: float
    y: float
    speed_x: float
    speed_y: float


class MatchStateMessage(BaseModel):
    event: str

    actual_tic: int
    total_tic: int

    user1_goals: int
    user2_goals: int

    ball: BallState
    players: list[MatchPlayerState]


class MatchCoachChange(BaseModel):
    club_id: int
    player_id: int
    behavior: str


# behavior changes made by the coaches (DT) and applied in this tic
class MatchCoachChangesMessage(BaseModel):
    event: Literal["coach_changes"] = "coach_changes"
    from_tic: int  # first tic in which the changes are in effect
    changes: list[MatchCoachChange]
