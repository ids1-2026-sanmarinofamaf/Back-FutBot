from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.club import Club


def get_by_user_id(db: Session, user_id: int) -> Club | None:
    return db.scalar(
        select(Club).where(Club.user_id == user_id)
    )