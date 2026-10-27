from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.league import LeagueState, LeaguePrivacy
from app.models.match import MatchState

from typing import Literal

from app.schemas.roster import RosterCreate


class LeagueCreate(BaseModel):
    """Body de POST /leagues.

    No lleva state (siempre arranca en POR_COMENZAR) ni creator_id (sale del token).
    The aliases are the field names of the contract agreed in the SRS.
    """
    name: str = Field(alias="nombre", min_length=1, max_length=50)
    # same limits as the frontend: up to 300 seconds and between 3 and 22 clubs
    match_duration: int = Field(alias="duracion_partido", gt=0, le=300)
    max_clubs: int = Field(alias="max_usuarios", ge=3, le=22)
    is_private: bool = Field(alias="es_privada")
    # plain password, it gets hashed in the service
    password: str | None = None
    roster: RosterCreate

    @property
    def privacy(self) -> LeaguePrivacy:
        return LeaguePrivacy.PRIVADA if self.is_private else LeaguePrivacy.PUBLICA

    # min_length counts spaces, so a name like "   " has to be rejected here
    @field_validator("name")
    @classmethod
    def check_name_not_blank(cls, name: str) -> str:
        name = name.strip()
        if not name:
            raise ValueError("League name cannot be blank")
        return name

    # private leagues must have a password, public ones must not
    # (an empty or blank string counts as no password, so public leagues may send password: "")
    @model_validator(mode="after")
    def check_privacy_password(self):
        has_password = bool(self.password and self.password.strip())
        if self.is_private and not has_password:
            raise ValueError("Private leagues must have a password")
        if not self.is_private and has_password:
            raise ValueError("Public leagues cannot have a password")
        return self


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

