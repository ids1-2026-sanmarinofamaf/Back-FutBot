
# app/repositories/behavior_repository.py
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models.behavior import Behavior

def get_available_by_name(db: Session, club_id: int, name: str) -> Behavior | None:
    return db.scalars(
        select(Behavior)
        .where(
            Behavior.name == name,
            or_(Behavior.is_default.is_(True), Behavior.club_id == club_id),
        )
        # si hay uno del club con el mismo nombre que un default, gana el del club
        .order_by(Behavior.is_default.asc())
    ).first()

def get_by_id(
    db: Session,
    behavior_id: int,
) -> Behavior | None:
    return db.get(Behavior, behavior_id)


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


def get_available_for_club(
    db: Session,
    club_id: int,
) -> list[Behavior]:
    # global defaults are available to every club, plus the club's own behaviors
    return list(
        db.scalars(
            select(Behavior)
            .where(
                or_(
                    Behavior.is_default.is_(True),
                    Behavior.club_id == club_id,
                )
            )
            .order_by(Behavior.id)
        ).all()
    )
