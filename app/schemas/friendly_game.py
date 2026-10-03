from pydantic import BaseModel, Field

from app.schemas.roster import RosterCreate
from app.models.friendly_game import FriendlyGameState


# Body
class FriendlyGameCreate(BaseModel):
    duration: int = Field(gt=0)
    roster: RosterCreate

# Response
class FriendlyGameCreateResponse(BaseModel):
    friendly_game_id: int
    roster_id: int



class FriendlyGameUpdate(BaseModel):
    state: FriendlyGameState


class FriendlyGameStartResponse(BaseModel):
    match_id: int

