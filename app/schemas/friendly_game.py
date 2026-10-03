from pydantic import BaseModel

from app.schemas.roster import RosterCreate
from app.models.friendly_game import FriendlyGameState


class FriendlyGameCreate(BaseModel):
    duration: int
    roster: RosterCreate


class FriendlyGameCreateResponse(BaseModel):
    friendly_game_id: int
    roster_id: int



class FriendlyGameUpdate(BaseModel):
    state: FriendlyGameState


class FriendlyGameStartResponse(BaseModel):
    match_id: int