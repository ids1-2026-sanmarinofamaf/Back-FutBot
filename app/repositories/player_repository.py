from sqlalchemy.orm import Session

from app.models.player import Player
def save(db, player: Player):
    db.add(player)
    db.flush()

def get_by_id(db: Session, player_id: int) -> Player | None:
    return db.get(Player, player_id)
    

    