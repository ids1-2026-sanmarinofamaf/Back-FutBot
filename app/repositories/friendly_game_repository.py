from sqlalchemy.orm import Session

from app.models.friendly_game import (
    FriendlyGame,
    FriendlyGameState,
)

from app.models.friendly_game_participation import (
    FriendlyGameParticipation,
    FriendlyGameRole,
)


# create and persist friendly game
def create(
    db: Session,
    duration: int,
    creator_id: int
) -> FriendlyGame:

    friendly_game = FriendlyGame(
        duration=duration,
        creator_id=creator_id
    )

    # use flush instead of commit to keep transaction control
    # outside this function, so we can rollback later
    db.add(friendly_game)
    db.flush()

    return friendly_game


# create and persist FriendlyGameParticipation
def create_participation(
    db: Session,
    friendly_game_id: int,
    club_id: int,
    roster_id: int,
    role: FriendlyGameRole,
) -> FriendlyGameParticipation:

    participation = FriendlyGameParticipation(
        friendly_game_id=friendly_game_id,
        club_id=club_id,
        roster_id=roster_id,
        role=role,
    )

    db.add(participation)
    db.flush()

    return participation

# get frienddly game by id
def get_by_id(
    db: Session,
    friendly_game_id: int
) -> FriendlyGame | None:
    return db.get(FriendlyGame, friendly_game_id)

# update state in db
def update_state(
    db: Session,
    friendly_game: FriendlyGame,
    state: FriendlyGameState,
) -> None:

    friendly_game.state = state
    db.flush()