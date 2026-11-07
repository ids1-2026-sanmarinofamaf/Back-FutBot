from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.club import Club


def get_by_user_id(db: Session, user_id: int) -> Club | None:
    return db.scalar(
        select(Club).where(Club.user_id == user_id)
    )

# update the club info in db
def update_club(
    db: Session,
    club: Club,
    new_name: str | None,
    new_avatar: str | None
) -> None:
    if new_name is not None:
        club.name = new_name

    if new_avatar is not None:
        club.avatar = new_avatar

    db.flush()
