from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.club_statistics import ClubStatistics

# update statistics after match
def increment_match_statistics(
    db: Session,
    club_id: int,
    points: int,
    won: int,
    drawn: int,
    lost: int,
    goals_for: int,
    goals_against: int,
) -> None:

    result = db.execute(
        update(ClubStatistics)
        .where(ClubStatistics.club_id == club_id)
        .values(
            total_points=ClubStatistics.total_points + points,
            matches_played=ClubStatistics.matches_played + 1,
            matches_won=ClubStatistics.matches_won + won,
            matches_drawn=ClubStatistics.matches_drawn + drawn,
            matches_lost=ClubStatistics.matches_lost + lost,
            goals_for=ClubStatistics.goals_for + goals_for,
            goals_against=ClubStatistics.goals_against + goals_against,
        )
    )
    # verify only one club was updated
    if result.rowcount != 1:
        raise LookupError(
            f"Statistics not found for club {club_id}"
        )

    db.flush()
