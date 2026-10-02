from sqlalchemy.orm import Session

from app.models.roster import Roster
from app.models.player_on_roster import PlayerOnRoster
from app.schemas.roster import RosterCreate

# save a roster in db
def save(db: Session, roster: Roster) -> None:
    db.add(roster)
    db.flush()