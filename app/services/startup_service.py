from app.database import SessionLocal
from app.repositories import friendly_game_repository
from app.repositories import league_repository

from app.services.league_runner import start_league_runner


def recover_interrupted_games() -> None:
    with SessionLocal() as db:
        try:
            friendly_game_repository.finalize_interrupted_games(db)
            db.commit()
        except Exception:
            db.rollback()
            raise


def recover_interrupted_leagues() -> None:
    with SessionLocal() as db:
        leagues = league_repository.get_started_leagues_ids(db)

    for league_id in leagues:
        start_league_runner(league_id)