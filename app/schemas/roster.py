from pydantic import BaseModel

from app.models.roster import Formation
from app.models.player_on_roster import RosterSlot

# classes for the contract with the API
# Body
class PlayerOnRosterCreate(BaseModel):
    player_id: int
    is_starter: bool
    slot: RosterSlot | None = None
    initial_behavior_id: int | None = None


class RosterCreate(BaseModel):
    formation: Formation
    players: list[PlayerOnRosterCreate]