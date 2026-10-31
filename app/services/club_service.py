from sqlalchemy.orm import Session

from app.repositories import club_repository
from app.schemas.club import ClubOut, ClubStatisticsOut, ClubUpdate


class ClubNotFound(Exception):
    pass

# get schema club info
def get_club(db: Session, user_id: int) -> ClubOut:
    club = club_repository.get_by_user_id(db, user_id)

    if club is None:
        raise ClubNotFound()

    stats = club.statistics

    if stats is None:
        raise ClubNotFound()

    return ClubOut(
        club_avatar=club.avatar,
        club_name=club.name,
        statistics=ClubStatisticsOut(
            total_points=stats.total_points,
            matches_played=stats.matches_played,
            matches_won=stats.matches_won,
            matches_drawn=stats.matches_drawn,
            matches_lost=stats.matches_lost,
            goals_for=stats.goals_for,
            goals_against=stats.goals_against,
            leagues_played=stats.leagues_played,
            leagues_won=stats.leagues_won
        )
    )

# update club using schema info
def update_club(
    db: Session,
    user_id: int,
    data: ClubUpdate
) -> None:
    club = club_repository.get_by_user_id(db, user_id)

    if club is None:
        raise ClubNotFound()

    try:
        club_repository.update_club(
            db=db,
            club=club,
            new_name=data.new_name,
            new_avatar=data.new_avatar
        )
        db.commit()

    except Exception:
        db.rollback()
        raise
