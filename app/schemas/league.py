from pydantic import BaseModel

from typing import Literal

from app.schemas.roster import RosterCreate

from app.models.league import LeagueState, LeaguePrivacy
from app.models.match import MatchState


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

class FixtureClub(BaseModel):
    club_id: int
    name: str


class FixtureMatchItem(BaseModel):
    match_id: int
    match_order: int
    state: MatchState
    local: FixtureClub
    visitante: FixtureClub


class StandingRow(BaseModel):
    club_id: int
    name: str
    points: int
    matches_played: int
    matches_won: int
    matches_drawn: int
    matches_lost: int
    goals_for: int
    goals_against: int
    goal_difference: int


class LeagueStartedEvent(BaseModel):
    # le sirve al front para distinguir league_started de otros eventos que lleguen por el mismo canal de liga.
    type: Literal["league_started"] = "league_started"
    league_id: int
    fixture: list[FixtureMatchItem]
    standings: list[StandingRow]


class LeagueDetail(BaseModel):
    league_id: int
    name: str
    state: LeagueState
    privacy: LeaguePrivacy
    current_participants: int
    capacity: int
    # only filled when the league is INICIADA
    fixture: list[FixtureMatchItem] | None = None
    standings: list[StandingRow] | None = None

