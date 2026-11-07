
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.game.active_matches import is_club_in_active_match
from app.game.behavior_validator import BehaviorValidationError, validate_coach_code
from app.game.default_behaviors import ATTACKER_NAME, DEFENDER_NAME, MIDFIELDER_NAME
from app.models.coach_behavior import CoachBehavior
from app.repositories import club_repository, coach_behavior_repository

# El router las traduce a códigos HTTP.

class ClubNotFound(Exception):
    pass
class ClubInActiveMatch(Exception):
    pass
    
class CoachBehaviorNameTaken(Exception):
    pass
class InvalidCoachCode(Exception):
    pass
class CoachBehaviorNotFound(Exception):
    pass

DEFAULTS = (ATTACKER_NAME, DEFENDER_NAME, MIDFIELDER_NAME)

def list_coach_behaviors(db: Session, user_id: int) -> list[CoachBehavior]:
    club = club_repository.get_by_user_id(db, user_id)

    if club is None:
        raise ClubNotFound("User does not have a club")

    return coach_behavior_repository.list_by_club(db, club.id)


def get_coach_behavior(db: Session, user_id: int, coach_behavior_id: int) -> CoachBehavior:
    club = club_repository.get_by_user_id(db, user_id)

    if club is None:
        raise ClubNotFound("User does not have a club")

    coach_behavior = coach_behavior_repository.get_by_id_for_club(
        db=db,
        club_id=club.id,
        coach_behavior_id=coach_behavior_id,
    )

    if coach_behavior is None:
        raise CoachBehaviorNotFound("Coach behavior not found.")

    return coach_behavior


def create_coach_behavior(db: Session, user_id: int, name: str, code: str) -> CoachBehavior:
 
    club = club_repository.get_by_user_id(db, user_id)

    if club is None:
        raise ClubNotFound("User does not have a club")
    
    if is_club_in_active_match(club.id):
        raise ClubInActiveMatch("User cannot perform this action while playing a live match.")
    
    if name in DEFAULTS:
        raise CoachBehaviorNameTaken("Coach behavior name matches a default behavior.")

    # static checks plus a dry-run of coach(); the code runs in a separate
    # process with a timeout, never inside the API process
    try:
        validate_coach_code(code)
    except BehaviorValidationError as error:
        raise InvalidCoachCode(str(error)) from error

    #CoachBehavior (id lo genera la base, club y rosters son relaciones)
    coach_behavior = CoachBehavior(
        club_id=club.id,
        name=name,
        code=code,
    )

    try:
        coach_behavior_repository.save(db, coach_behavior)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise CoachBehaviorNameTaken("Coach behavior name already exists.") from error
    except Exception:
        db.rollback()
        raise

    db.refresh(coach_behavior)

    return coach_behavior


def delete_coach_behavior(db: Session, user_id: int, coach_behavior_id: int) -> None:
    
    club = club_repository.get_by_user_id(db, user_id)

    if club is None:
        raise ClubNotFound("User does not have a club")

    if is_club_in_active_match(club.id):
        raise ClubInActiveMatch("User cannot perform this action while playing a live match.")

    coach_behavior = coach_behavior_repository.get_by_id_for_club(
        db=db,
        club_id=club.id,
        coach_behavior_id=coach_behavior_id,
    )

    if coach_behavior is None:
        raise CoachBehaviorNotFound("Coach behavior not found.")

    try:
        coach_behavior_repository.delete(db, coach_behavior)
        db.commit()
    except Exception:
        db.rollback()
        raise


# used by every flow that creates a roster; each service wraps the ValueError in its own error
def validate_coach_behavior(db: Session, club_id: int, coach_behavior_id: int | None) -> None:
    if coach_behavior_id is None:
        return

    coach_behavior = coach_behavior_repository.get_by_id_for_club(
        db=db,
        club_id=club_id,
        coach_behavior_id=coach_behavior_id,
    )

    # same message for a nonexistent id and another club's id
    if coach_behavior is None:
        raise ValueError("Coach behavior doesn't exist.")
