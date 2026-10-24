from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

from app.models.league import League, LeagueState
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


def get_visible_leagues(
    db:Session,
) -> list[League]:
    return list(
        db.scalars(
            select(League)
            .options(
                selectinload(League.league_participations),
            )
            .where(
                League.state.in_(
                    [
                        LeagueState.POR_COMENZAR,
                        LeagueState.INICIADA,
                    ]
                )
            )
            .order_by(League.id)
        ).all()
    )
