from pydantic import BaseModel

from app.schemas.roster import RosterCreate


class LeagueJoin(BaseModel):
    roster: RosterCreate
    password: str | None = None

class LeagueJoinResponse(BaseModel):
    league_id: int
    club_id: int
    roster_id: int