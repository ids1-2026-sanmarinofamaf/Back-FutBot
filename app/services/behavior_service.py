from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.repositories import (
    behavior_repository,
    club_repository
)


def list_behaviors(db: Session, user_id: int) -> list[Behavior]:
    club = club_repository.get_by_user_id(db, user_id)

    if club is None:
        raise ValueError("User does not have a club")

    return behavior_repository.get_available_for_club(db, club.id)
