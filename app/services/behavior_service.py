from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.repositories import (
    behavior_repository,
    club_repository
)
from app.game.behavior_validator import (
    BehaviorValidationError, # useful for api/behaviors.py
    validate_behavior_code
)

def list_behaviors(db: Session, user_id: int) -> list[Behavior]:
    club = club_repository.get_by_user_id(db, user_id)

    if club is None:
        raise ValueError("User does not have a club")

    return behavior_repository.get_available_for_club(db, club.id)

# Get a behavior by ID if it is default or belongs to the user's club
def get_behavior(db: Session, user_id: int, behavior_id: int) -> Behavior:
    club = club_repository.get_by_user_id(db, user_id)

    if club is None:
        raise ValueError("User does not have a club")

    behavior = behavior_repository.get_available_by_id(
        db=db,
        club_id=club.id,
        behavior_id=behavior_id,
    )

    if behavior is None:
        raise LookupError("Behavior not found")

    return behavior


def get_behavior_by_name(db: Session, user_id: int, name: str) -> Behavior | None:
    club = club_repository.get_by_user_id(db, user_id)

    if club is None:
        raise ValueError("User does not have a club")

    return behavior_repository.get_available_by_name(db, club.id, name)

def validate_behavior(code: str) -> bool:
    """
    Validate player behavior Python source code.

    Args:
        code: Raw Python source code defining the behavior.

    Returns:
        True if the behavior code passes all validation stages.

    Raises:
        BehaviorValidationError: If the behavior code fails validation.
    """
    return validate_behavior_code(code)