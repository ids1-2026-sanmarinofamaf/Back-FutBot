from pydantic import BaseModel


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