from pydantic import BaseModel

from app.schemas.roster import RosterCreate
from app.models.league import LeagueState, LeaguePrivacy


class LeagueJoin(BaseModel):
    roster: RosterCreate
    password: str | None = None


class LeagueJoinResponse(BaseModel):
    league_id: int
    club_id: int
    roster_id: int


class LeagueSessionItem(BaseModel):
    league_id: int
    name: str
    current_participants: int
    capacity: int
    privacy: LeaguePrivacy
    state: LeagueState


class LeaguesSessionPayload(BaseModel):
    leagues: list[LeagueSessionItem]
