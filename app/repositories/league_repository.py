from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.league import League
from app.models.league_participation import LeagueParticipation

# to verify that the league exists
def get_by_id(
    db: Session,
    league_id: int,
) -> League | None:
    return db.get(League, league_id)


def count_participations(
    db: Session,
    league_id: int,
) -> int:
    return db.scalar(
        select(func.count())
        .select_from(LeagueParticipation)
        .where(
            LeagueParticipation.league_id
            == league_id,
        )
    ) or 0