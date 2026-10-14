from app.database import SessionLocal
from app.repositories import friendly_game_repository


def recover_interrupted_games() -> None:
    with SessionLocal() as db:
        try:
            friendly_game_repository.finalize_interrupted_games(db)
            db.commit()
        except Exception:
            db.rollback()
            raise
