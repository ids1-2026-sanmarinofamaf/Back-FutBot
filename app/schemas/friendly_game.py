from pydantic import BaseModel, Field

from app.schemas.roster import RosterCreate

# classes for the contract with the API
# Body
class FriendlyGameCreate(BaseModel):
    duration: int = Field(gt=0)
    roster: RosterCreate

# Response
class FriendlyGameCreateResponse(BaseModel):
    friendly_game_id: int
    roster_id: int

# join
class FriendlyGameJoin(BaseModel):
    roster: RosterCreate

class FriendlyGameJoinResponse(BaseModel):
    friendly_game_id: int
    participation_id: int
    roster_id: int