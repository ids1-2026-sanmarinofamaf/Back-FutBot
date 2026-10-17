from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.league_participation import LeagueParticipation


# to check whether the club participates in that league
def get_participation_by_club_and_league(
    db: Session,
    league_id: int,
    club_id: int,
) -> LeagueParticipation | None:
    return db.scalar(
        select(LeagueParticipation)
        .where(
            LeagueParticipation.league_id == league_id,
            LeagueParticipation.club_id == club_id,
        )
    )

# to delete participation in the db
def delete_participation(
    db: Session,
    participation: LeagueParticipation,
) -> None:
    db.delete(participation)
    db.flush()


# create and persist leagueParticipation
def create_participation(
    db: Session,
    league_id: int,
    club_id: int,
    roster_id: int,
) -> LeagueParticipation:
    participation = LeagueParticipation(
        league_id=league_id,
        club_id=club_id,
        roster_id=roster_id,
    )

    db.add(participation)
    db.flush()

    return participation