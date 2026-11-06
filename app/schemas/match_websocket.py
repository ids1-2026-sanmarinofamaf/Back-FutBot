from pydantic import BaseModel
from typing import Literal


class MatchPlayerState(BaseModel):
    player_id: int
    x: float
    y: float
    is_on_field: bool
    team: str
    current_behavior_id: int | None = None


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

    current_period: int
    is_paused: bool
    pause_type: Literal["hydration", "halftime"] | None
    substitution_window_open: bool

    ball: BallState
    players: list[MatchPlayerState]


class MatchPauseStartedMessage(BaseModel):
    event: Literal["pause_started"] = "pause_started"
    pause_type: Literal["hydration", "halftime"]
    duration: float
    planning_duration: float


class MatchSubstitutionWindowClosedMessage(BaseModel):
    event: Literal["substitution_window_closed"] = "substitution_window_closed"
    pause_type: Literal["hydration", "halftime"]


class MatchPauseFinishedMessage(BaseModel):
    event: Literal["pause_finished"] = "pause_finished"
    pause_type: Literal["hydration", "halftime"]

class MatchTeamInfo(BaseModel):
    club_id: int
    club_name: str
    coach_behavior_name: str | None = None


class MatchPlayerInfo(BaseModel):
    player_id: int
    name: str
    team: Literal["A", "B"]
    club_id: int
    shirt_number: int


class MatchInfoMessage(BaseModel):
    event: Literal["match_info"] = "match_info"
    match_id: int
    team_a: MatchTeamInfo
    team_b: MatchTeamInfo
    players: list[MatchPlayerInfo]
