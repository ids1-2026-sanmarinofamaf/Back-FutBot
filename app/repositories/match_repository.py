from sqlalchemy import text
from sqlalchemy.orm import Session


def get_next_match_id(db: Session) -> int:
    return db.execute(
        text("SELECT nextval('match_id_seq')")
    ).scalar_one()
