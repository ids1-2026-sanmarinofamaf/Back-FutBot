
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.game.active_matches import is_club_in_active_match
from app.game.behavior_compiler import BehaviorCompiler, BehaviorCompilationError
from app.game.default_behaviors import ATTACKER_NAME, DEFENDER_NAME, MIDFIELDER_NAME
from app.game.models.behavior_definition import BehaviorDefinition
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


#crear:
#el club tiene que existir;
#si is_club_in_active_match → 403;
#si el nombre es igual a un default → 409;
#el código tiene que definir coach();
#si salta IntegrityError → 409 por nombre repetido;
#listar: solo los DT del club;
#borrar: si hay partido en curso → 403; si no es del club → 404.

DEFAULTS = (ATTACKER_NAME, DEFENDER_NAME, MIDFIELDER_NAME)

def list_coach_behaviors(db: Session, user_id: int) -> list[CoachBehavior]:
    club = club_repository.get_by_user_id(db, user_id)

    if club is None:
        raise ClubNotFound("User does not have a club")

    return coach_behavior_repository.list_by_club(db, club.id)


def create_coach_behavior(db: Session, user_id: int, name: str, code: str) -> CoachBehavior:
 
    club = club_repository.get_by_user_id(db, user_id)

    if club is None:
        raise ClubNotFound("User does not have a club")
    
    if is_club_in_active_match(club.id):
        raise ClubInActiveMatch("User cannot perform this action while playing a live match.")
    
    if name in DEFAULTS:
        raise CoachBehaviorNameTaken("Coach behavior name matches a default behavior.")

    # 4. compilar con entrypoint="coach"; si falla → InvalidCoachCode
    # todavía no hay id en la base, el compilador solo lo usa para los mensajes de error
    # NOTE: compiling runs exec() on user code inside the API process.
    # Top-level code (e.g. an infinite loop) would block this request.
    compiler = BehaviorCompiler()
    definition = BehaviorDefinition(
        id=0,
        code=code,
    )

    try:
        compiler.compile(definition, entrypoint="coach")
    except BehaviorCompilationError as error:
        raise InvalidCoachCode("Code must define a callable coach().") from error

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
