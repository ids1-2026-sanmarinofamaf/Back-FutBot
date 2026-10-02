from sqlalchemy.orm import Session

from app.models.roster import Roster


# save a roster in db
def save(db: Session, roster: Roster) -> None:
    db.add(roster)
    db.flush()