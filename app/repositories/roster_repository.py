from sqlalchemy.orm import Session

from app.models.roster import Roster


# save a roster in db
def save(db: Session, roster: Roster) -> None:
    db.add(roster)
    db.flush()

# delete a roster from db
def delete_roster(db: Session, roster: Roster) -> None:
    db.delete(roster)
    db.flush()