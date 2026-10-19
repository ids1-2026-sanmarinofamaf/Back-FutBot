from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.league import League, LeagueState
from app.models.league_participation import LeagueParticipation

# to verify that the league exists
def get_by_id(
    db: Session,
    league_id: int,
) -> League | None:
    return db.get(League, league_id)


def update_state(
    db: Session,
    league: League,
    state: LeagueState,
) -> None:
    league.state = state
    db.flush()