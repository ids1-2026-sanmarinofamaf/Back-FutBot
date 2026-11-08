from typing import Literal
from pydantic import (
    BaseModel,
    Field,
    AwareDatetime,
)

from app.schemas.league import (
    LeagueDetail,
    MatchScore,
    StandingRow,
)

# the info of the user
class LeagueLobbyUser(BaseModel):
    club_id: int
    user_name: str
    avatar: str
    is_creator: bool

# the info that will be sended to the user when he join a new league
class LeagueLobbyState(BaseModel):
    type: Literal["lobby_state"] = "lobby_state"
    league_id: int
    state: str
    current_users: int
    users: list[LeagueLobbyUser]


class LeagueUserEvent(BaseModel):
    type: Literal["user_joined", "user_left"]
    league_id: int
    user: LeagueLobbyUser


class LeagueStateEvent(BaseModel):
    type: Literal["league_state"] = "league_state"
    data: LeagueDetail


class LeagueRoundStartedEvent(BaseModel):
    type: Literal["league_round_started"] = "league_round_started"
    league_id: int = Field(ge=1)
    round: int = Field(ge=1)
    match_ids: list[int] = Field(min_length=1)


class LeagueMatchResult(BaseModel):
    match_id: int = Field(ge=1)
    state: Literal["FINALIZADO"] = "FINALIZADO"
    score: MatchScore


class LeagueRoundFinishedEvent(BaseModel):
    type: Literal["league_round_finished"] = "league_round_finished"
    league_id: int = Field(ge=1)
    round: int = Field(ge=1)
    results: list[LeagueMatchResult] = Field(min_length=1)
    standings: list[StandingRow]
    break_ends_at: AwareDatetime | None


class LeagueFinishedEvent(BaseModel):
    type: Literal["league_finished"] = "league_finished"
    league_id: int = Field(ge=1)
    state: Literal["FINALIZADA"] = "FINALIZADA"


class LeagueCancelledEvent(BaseModel):
    type: Literal["league_cancelled"] = "league_cancelled"
    league_id: int = Field(ge=1)
