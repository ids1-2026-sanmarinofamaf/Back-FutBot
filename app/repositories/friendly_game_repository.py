from sqlalchemy.orm import Session

from app.models.friendly_game import FriendlyGame
from app.models.friendly_game_participation import FriendlyGameParticipation

# create and persist friendly game
def create(db: Session, duration: int, creator_id: int) -> FriendlyGame:

    friendly_game = FriendlyGame(duration=duration, creator_id=creator_id)
    # use flush instead of commit to keep transaction control outside this function, so we can rollback later
    db.add(friendly_game)
    db.flush()

    return friendly_game

# create and persist friendlyGameParticipation with the reference to friendly_game_id
def create_participation(
    db: Session,
    friendly_game_id: int,
    user_id: int,
    roster_id: int
) -> FriendlyGameParticipation:

    participation = FriendlyGameParticipation(
        friendly_game_id=friendly_game_id,
        user_id=user_id,
        roster_id=roster_id
    )
    # use flush instead of commit to keep transaction control outside this function, so we can rollback later
    db.add(participation)
    db.flush()

    return participation