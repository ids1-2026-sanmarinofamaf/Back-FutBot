from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from app.models.behavior import Behavior

# get behaviors of 2 clubs

def get_by_club_ids(
    db: Session,
    club_ids: set[int],
) -> list[Behavior]:

    return list(
        db.scalars(
            select(Behavior).where(
                or_(
                    Behavior.club_id.in_(club_ids),
                    Behavior.is_default.is_(True),
                )
            )
        )
    )