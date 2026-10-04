# app/repositories/behavior_repository.py
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models.behavior import Behavior

def get_by_id(
    db: Session,
    behavior_id: int,
) -> Behavior | None:
    return db.get(Behavior, behavior_id)

def get_available_for_club(db: Session, club_id: int) -> list[Behavior]:
    # global defaults are available to every club, plus the club's own behaviors
    return list(db.scalars(
        select(Behavior)
        .where(or_(Behavior.is_default.is_(True), Behavior.club_id == club_id))
        .order_by(Behavior.id)
    ).all())

