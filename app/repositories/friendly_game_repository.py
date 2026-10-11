from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select, func

from app.models.friendly_game import (
    FriendlyGame,
    FriendlyGameState,
)

from app.models.friendly_game_participation import (
    FriendlyGameParticipation,
    FriendlyGameRole,
)



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
    # use flush instead of commit to keep transaction control outside this function, so we can rollback later


def count_participations(
    db: Session,
    friendly_game_id: int
) -> int:

    return db.scalar(
        select(func.count(FriendlyGameParticipation.id))
        .where(
            FriendlyGameParticipation.friendly_game_id
            == friendly_game_id
        )
    ) or 0


def get_participation_by_club(
    db: Session,
    friendly_game_id: int,
    club_id: int
) -> FriendlyGameParticipation | None:

    return db.scalar(
        select(FriendlyGameParticipation)
        .where(
            FriendlyGameParticipation.friendly_game_id
            == friendly_game_id,
            FriendlyGameParticipation.club_id == club_id,
        )
    )

# get only matches that will appear on the list of friendly games avaivable
def get_visible_friendly_games(
    db: Session,
) -> list[FriendlyGame]:

    return list(
        db.scalars(
            select(FriendlyGame)
            .options(
                # for creator
                joinedload(FriendlyGame.creator),
                # for capactity
                selectinload(FriendlyGame.participations),
            )
            .where(
                FriendlyGame.state.in_(
                    [
                        FriendlyGameState.POR_COMENZAR,
                        FriendlyGameState.JUGANDO,
                    ]
                )
            )
            .order_by(FriendlyGame.id)
        ).all()
    )