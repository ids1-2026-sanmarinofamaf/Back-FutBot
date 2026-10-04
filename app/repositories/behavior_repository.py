from sqlalchemy.orm import Session

from app.models.behavior import Behavior


def get_by_id(
    db: Session,
    behavior_id: int,
) -> Behavior | None:
    return db.get(Behavior, behavior_id)