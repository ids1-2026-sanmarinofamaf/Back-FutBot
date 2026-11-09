from pydantic import BaseModel
from typing import Literal

from app.game.penalties import PenaltySide


class MatchPlayerState(BaseModel):
    player_id: int
    x: float
    y: float
    is_on_field: bool
    team: str
    current_behavior_id: int | None = None
    current_behavior_name: str | None = None


class BallState(BaseModel):
    x: float
    y: float
    speed_x: float
    speed_y: float


class MatchPendingSubstitution(BaseModel):
    player_out_id: int
    player_in_id: int


class MatchStateMessage(BaseModel):
    event: str

    actual_tic: int
    total_tic: int

    user1_goals: int
    user2_goals: int

    current_period: int = 1
    is_paused: bool = False
    pause_type: Literal["hydration", "halftime"] | None = None
    substitution_window_open: bool = True
    pending_substitution: MatchPendingSubstitution | None = None

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


class MatchCoachSubstitution(BaseModel):
    club_id: int
    player_out_id: int
    player_in_id: int


# substitutions requested by the coaches (DT) and executed in this break
class MatchCoachSubstitutionsMessage(BaseModel):
    event: Literal["coach_substitutions"] = "coach_substitutions"
    changes: list[MatchCoachSubstitution]

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
    my_club_id: int | None = None
    team_a: MatchTeamInfo
    team_b: MatchTeamInfo
    players: list[MatchPlayerInfo]


class PenaltyShootoutStartedMessage(BaseModel):
    event: Literal["penalty_shootout_started"] = "penalty_shootout_started"
    duration: float


class PenaltyTurnStartedMessage(BaseModel):
    event: Literal["penalty_turn_started"] = "penalty_turn_started"
    turn: int
    club_id: int
    kicker: int
    score_club_a: int
    score_club_b: int
    remaining_seconds: float


class PenaltyResultMessage(BaseModel):
    event: Literal["penalty_result"] = "penalty_result"
    turn: int
    club_id: int
    kicker: int
    kick_side: PenaltySide
    save_side: PenaltySide
    is_goal: bool
    score_club_a: int
    score_club_b: int
    duration: float


class PenaltyHistoryMessage(BaseModel):
    event: Literal["penalty_history"] = "penalty_history"
    results: list[PenaltyResultMessage]


class PenaltyShootoutFinishedMessage(BaseModel):
    event: Literal["penalty_shootout_finished"] = "penalty_shootout_finished"
    winner_club_id: int
    score_club_a: int
    score_club_b: int
