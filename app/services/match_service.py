from sqlalchemy.orm import Session

from app.game.models.match import Match
from app.game.models.behavior_definition import BehaviorDefinition
from app.repositories import behavior_repository

# load behaviors in memory for the match
def load_match_behaviors(
    db: Session,
    match: Match,
) -> list[BehaviorDefinition]:

    club_ids = {
        match.participation_a.club_id,
        match.participation_b.club_id,
    }

    behaviors = behavior_repository.get_by_club_ids(
        db=db,
        club_ids=club_ids,
    )

    return [
        BehaviorDefinition(
            id=behavior.id,
            code=behavior.code,
        )
        for behavior in behaviors
    ]