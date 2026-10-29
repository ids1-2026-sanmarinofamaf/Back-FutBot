from app.models.league import League, LeaguePrivacy
from sqlalchemy.orm import Session

from app.repositories import club_statistics_repository

# this method should be called at the end of a league match, verifying that it is a public league. 
# since the "start league" functionality has not yet been implemented, i am leaving this for whoever is tasked with implementing it.
def update_statistics(
    db: Session,
    league: League,
    club_a_id: int,
    club_b_id: int,
    goals_a: int,
    goals_b: int,
) -> None:

    if league.privacy != LeaguePrivacy.PUBLICA:
        return

    # determine match result
    if goals_a > goals_b:
        points_a, points_b = 3, 0
        won_a, won_b = 1, 0
        drawn_a, drawn_b = 0, 0
        lost_a, lost_b = 0, 1

    elif goals_a < goals_b:
        points_a, points_b = 0, 3
        won_a, won_b = 0, 1
        drawn_a, drawn_b = 0, 0
        lost_a, lost_b = 1, 0

    else:
        points_a, points_b = 1, 1
        won_a, won_b = 0, 0
        drawn_a, drawn_b = 1, 1
        lost_a, lost_b = 0, 0

    # update club a statistics
    club_statistics_repository.increment_match_statistics(
        db=db,
        club_id=club_a_id,
        points=points_a,
        won=won_a,
        drawn=drawn_a,
        lost=lost_a,
        goals_for=goals_a,
        goals_against=goals_b,
    )

    # ppdate club b statistics
    club_statistics_repository.increment_match_statistics(
        db=db,
        club_id=club_b_id,
        points=points_b,
        won=won_b,
        drawn=drawn_b,
        lost=lost_b,
        goals_for=goals_b,
        goals_against=goals_a,
    )

def update_league_statistics(
    db: Session,
    club_ids: list[int],
    winner_id: int,
) -> None:

    for club_id in club_ids:
        club_statistics_repository.increment_league_statistics(
            db=db,
            club_id=club_id,
            won=(club_id == winner_id),
        )
