from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.player import Player


def save(db, player: Player):
    db.add(player)
    db.flush()


def get_by_id(db: Session, player_id: int) -> Player | None:
    return db.get(Player, player_id)


def get_by_club_id(db: Session, club_id: int) -> list[Player]:
    return list(db.scalars(
        select(Player)
        .where(Player.club_id == club_id)
        .order_by(Player.id)
    ).all())
