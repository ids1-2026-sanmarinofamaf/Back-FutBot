from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.models.friendly_game import FriendlyGame, FriendlyGameState
from app.models.friendly_game_participation import FriendlyGameParticipation
from app.models.league import League, LeagueState
from app.models.league_participation import LeagueParticipation
from app.models.player_on_roster import PlayerOnRoster
from app.repositories import (
    behavior_repository,
    club_repository
)
from app.schemas.behavior import BehaviorIn
from app.game.active_matches import is_club_in_active_match
from app.game.behavior_validator import (
    BehaviorValidationError, # useful for api/behaviors.py
    validate_behavior_code
)

class DefaultBehaviorModificationError(Exception):
    """Raised when a user attempts to modify a read-only default behavior."""


class ActiveCompetitionError(Exception):
    """Raised when an operation cannot be performed because the club has an active match or competition."""


def _validate_behavior_name(name: str) -> str:
    """
    Validate and normalize a behavior name.

    Args:
        name: Raw behavior name string.

    Returns:
        Trimmed behavior name.

    Raises:
        ValueError: If the name is empty, whitespace-only, shorter than 3
            characters, or exceeds 255 characters.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Behavior name cannot be empty")

    clean_name = name.strip()
    if len(clean_name) < 3:
        raise ValueError("Behavior name must be at least 3 characters long")
    if len(clean_name) > 255:
        raise ValueError("Behavior name cannot exceed 255 characters")

    return clean_name

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

def create_behavior(db: Session, user_id: int, data: BehaviorIn) -> Behavior:
    """
    Validate and create a new custom behavior for the user's club.

    Args:
        db: Active SQLAlchemy database session.
        user_id: Authenticated user identifier.
        data: Behavior creation payload containing name and code.

    Returns:
        Newly persisted Behavior ORM instance.

    Raises:
        ValueError: If the user has no club or the behavior name is invalid.
        BehaviorValidationError: If the behavior source code fails validation.
    """
    try:
        club = club_repository.get_by_user_id(db, user_id)
        if club is None:
            raise ValueError("User does not have a club")

        clean_name = _validate_behavior_name(data.name)
        validate_behavior_code(data.code)

        behavior = Behavior(
            club_id=club.id,
            name=clean_name,
            code=data.code,
            is_default=False,
        )

        behavior_repository.save(db, behavior)
        db.commit()
        return behavior
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Behavior name already exists") from exc
    except Exception:
        db.rollback()
        raise

def update_behavior(
    db: Session,
    user_id: int,
    behavior_id: int,
    data: BehaviorIn,
) -> Behavior:
    """
    Validate and update an existing custom behavior owned by the user's club.

    Args:
        db: Active SQLAlchemy database session.
        user_id: Authenticated user identifier.
        behavior_id: Identifier of the behavior to update.
        data: Behavior update payload containing the new name and code.

    Returns:
        Updated Behavior ORM instance.

    Raises:
        ValueError: If the user has no club or the behavior name is invalid.
        LookupError: If the behavior does not exist or belongs to another club.
        DefaultBehaviorModificationError: If the target behavior is a system default.
        BehaviorValidationError: If the behavior source code fails validation.
    """
    try:
        club = club_repository.get_by_user_id(db, user_id)
        if club is None:
            raise ValueError("User does not have a club")

        behavior = behavior_repository.get_available_by_id(
            db=db,
            club_id=club.id,
            behavior_id=behavior_id
        )

        if behavior is None:
            raise LookupError("Behavior not found")

        if behavior.is_default:
            raise DefaultBehaviorModificationError(
                "Default behaviors cannot be modified"
            )
        
        clean_name = _validate_behavior_name(data.name)
        validate_behavior_code(data.code)

        behavior.name = clean_name
        behavior.code = data.code

        behavior_repository.save(db, behavior)
        db.commit()
        return behavior
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Behavior name already exists") from exc
    except Exception:
        db.rollback()
        raise


def _has_active_league(db: Session, club_id: int) -> bool:
    stmt = (
        select(LeagueParticipation.league_id)
        .join(League, LeagueParticipation.league_id == League.id)
        .where(
            LeagueParticipation.club_id == club_id,
            League.state.in_([LeagueState.POR_COMENZAR, LeagueState.INICIADA]),
        )
    )
    return db.scalar(stmt) is not None


def _has_active_friendly_game(db: Session, club_id: int) -> bool:
    stmt = (
        select(FriendlyGameParticipation.id)
        .join(FriendlyGame, FriendlyGameParticipation.friendly_game_id == FriendlyGame.id)
        .where(
            FriendlyGameParticipation.club_id == club_id,
            FriendlyGame.state.in_([FriendlyGameState.POR_COMENZAR, FriendlyGameState.JUGANDO]),
        )
    )
    return db.scalar(stmt) is not None


def _unassign_behavior_from_rosters(db: Session, behavior_id: int) -> None:
    stmt = (
        update(PlayerOnRoster)
        .where(PlayerOnRoster.initial_behavior_id == behavior_id)
        .values(initial_behavior_id=None)
    )
    db.execute(stmt)


def delete_behavior(
    db: Session,
    user_id: int,
    behavior_id: int,
) -> None:
    """
    Delete a custom behavior owned by the authenticated user's club.

    Args:
        db: Active SQLAlchemy database session.
        user_id: Authenticated user identifier.
        behavior_id: Identifier of the behavior to delete.

    Raises:
        ValueError: If the user does not have an associated club.
        LookupError: If the behavior does not exist or belongs to another club.
        DefaultBehaviorModificationError: If attempting to delete a system default behavior.
        ActiveCompetitionError: If the club is in an active match, league, or friendly game.
    """
    try:
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

        if behavior.is_default:
            raise DefaultBehaviorModificationError(
                "Default behaviors cannot be modified"
            )

        if is_club_in_active_match(club.id):
            raise ActiveCompetitionError(
                "No se puede realizar esta acción mientras se participe en un partido o competencia activa."
            )

        if _has_active_league(db, club.id):
            raise ActiveCompetitionError(
                "No se puede realizar esta acción mientras se participe en un partido o competencia activa."
            )

        if _has_active_friendly_game(db, club.id):
            raise ActiveCompetitionError(
                "No se puede realizar esta acción mientras se participe en un partido o competencia activa."
            )

        _unassign_behavior_from_rosters(db, behavior.id)
        behavior_repository.delete(db, behavior)
        db.commit()
    except Exception:
        db.rollback()
        raise

        