from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.coach_behavior import CoachBehavior


def list_by_club(
    db: Session,
    club_id: int,
) -> list[CoachBehavior]:
    return list(
        db.scalars(
            select(CoachBehavior)
            .where(CoachBehavior.club_id == club_id)
            .order_by(CoachBehavior.id)
        ).all()
    )


# returns None if the coach behavior does not exist or belongs to another club
def get_by_id_for_club(
    db: Session,
    club_id: int,
    coach_behavior_id: int,
) -> CoachBehavior | None:
    return db.scalar(
        select(CoachBehavior).where(
            CoachBehavior.id == coach_behavior_id,
            CoachBehavior.club_id == club_id,
        )
    )


# flush so that IntegrityError (duplicated name) is raised here
def save(db: Session, coach_behavior: CoachBehavior) -> None:
    db.add(coach_behavior)
    db.flush()


def delete(db: Session, coach_behavior: CoachBehavior) -> None:
    db.delete(coach_behavior)
    db.flush()
