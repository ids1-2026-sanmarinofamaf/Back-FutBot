from sqlalchemy.orm import Session

from app.schemas.player import PlayerCreate
from app.models.player import Player
from app.repositories import (
    player_repository,
    club_repository
)


def create_player(db: Session, user_id: int, data: PlayerCreate):
    try:
        # obtain club
        club = club_repository.get_by_user_id(db,user_id)

        if club is None:
            raise ValueError("User does not have a club")

        player = Player(
        club_id=club.id,
        name=data.name,
        power=data.power,
        agility=data.agility,
        control=data.control,
        speed=data.speed,
        strength=data.strength,
        )

        
        # save player on db
        player_repository.save(db, player)

        # Commit everything together
        db.commit()

        return player

    # if an error occurred, we cancel the transaction.
    except Exception:
        db.rollback()
        raise

def get_player(db: Session, user_id: int, player_id: int) -> Player:
    club = club_repository.get_by_user_id(db, user_id)

    if club is None:
        raise ValueError("User does not have a club")

    player = player_repository.get_by_id(db, player_id)

    # a player from another club is treated as not found
    if player is None or player.club_id != club.id:
        raise LookupError("Player not found")

    return player
