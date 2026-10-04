from sqlalchemy.orm import Session
from app.database import SessionLocal
from sqlalchemy.exc import IntegrityError

from app.models.roster import Roster
from app.models.player_on_roster import PlayerOnRoster

from app.schemas.friendly_game import FriendlyGameCreate, FriendlyGameJoin
from app.models.friendly_game import FriendlyGameState
from app.models.friendly_game_participation import FriendlyGameRole

from app.game.models.match import Match
from app.game.models.match_participation import MatchParticipation
from app.game.models.player_in_match import PlayerInMatch
from app.game.models.ball import Ball

from app.game.formations import FORMATION_POSITIONS
from app.game.constants import FIELD_WIDTH, FIELD_HEIGHT, TICS_PER_SECOND

from app.services.match_service import (
    load_match_behaviors,
    start_match,
)

from app.services import session_websocket_service

from app.repositories import (
    friendly_game_repository,
    roster_repository,
    player_repository,
    behavior_repository,
    club_repository,
)

# classes for distinguishing exceptions
class FriendlyGameNotFoundError(Exception):
    pass


class FriendlyGameForbiddenError(Exception):
    pass

# helper for create playerInMatch
def _create_player_in_match(
    db: Session,
    player_on_roster: PlayerOnRoster,
    formation,
    mirror_position: bool,
) -> PlayerInMatch:
    # obtain the player, which is useful for the PACSS
    player = player_repository.get_by_id(db,player_on_roster.player_id)

    if player is None:
        raise ValueError("Player does not exist")

    # substitutes do not have a starting field position
    if not player_on_roster.is_starter:
        starting_position = None
        position = (0.0, 0.0)

    else:
        starting_position = FORMATION_POSITIONS[formation][player_on_roster.slot]

        # FORMATION_POSITIONS defines one side of the field.
        # The second team uses the mirrored coordinate.
        if mirror_position:
            starting_position = (
                FIELD_WIDTH - starting_position[0],
                starting_position[1],
            )

        position = starting_position
    # build the playerInMatch
    return PlayerInMatch(
        player_id=player.id,

        position=position,
        velocity=(0.0, 0.0),

        starting_position=starting_position,

        power=player.power,
        agility=player.agility,
        control=player.control,
        speed=player.speed,
        strength=player.strength,

        current_behavior_id=(
            player_on_roster.initial_behavior_id
            if player_on_roster.is_starter
            else None
        ),

        is_on_field=player_on_roster.is_starter,
    )

def _create_match_participation(
    db: Session,
    friendly_participation,
    mirror_position: bool,
) -> MatchParticipation:

    roster = friendly_participation.roster

    players = [
        _create_player_in_match(
            db=db,
            player_on_roster=player_on_roster,
            formation=roster.formation,
            mirror_position=mirror_position,
        )
        for player_on_roster in roster.players
    ]

    return MatchParticipation(
        club_id=friendly_participation.club_id,
        roster_id=friendly_participation.roster_id,
        players=players,
    )
class FriendlyGameNotFound(Exception):
    pass


class FriendlyGameNotAvailable(Exception):
    pass


class FriendlyGameFull(Exception):
    pass


class AlreadyParticipating(Exception):
    pass


class InvalidRoster(Exception):
    pass


def create_friendly_game(db: Session, user_id: int, data: FriendlyGameCreate):
    try:
        # obtain club
        club = club_repository.get_by_user_id(db,user_id)

        if club is None:
            raise ValueError("User does not have a club")

        # create roster object with the data
        roster = Roster(
            club_id=club.id,
            formation=data.roster.formation
        )

        roster.players = [
            PlayerOnRoster(
                player_id=p.player_id,
                is_starter=p.is_starter,
                slot=p.slot,
                initial_behavior_id=p.initial_behavior_id
            )
            for p in data.roster.players
        ]

        # validate the roster
        roster.validate_roster()

        # playerOnRoster validations
        for p in data.roster.players:
            player = player_repository.get_by_id(db, p.player_id)

            if player is None:
                raise ValueError("Player does not exist")

            if player.club_id != club.id:
                raise ValueError("Player does not belong to user's club")

            if p.initial_behavior_id is not None:
                behavior = behavior_repository.get_by_id(db,p.initial_behavior_id)

                if behavior is None:
                    raise ValueError("Behavior does not exist")

                if not behavior.is_default and behavior.club_id != club.id:
                    raise ValueError("Behavior does not belong to user's club")


        # save roster on db
        roster_repository.save(db,roster)

        # create friendly game
        friendly_game = friendly_game_repository.create(
            db=db,
            duration=data.duration,
            creator_id=club.id
        )

        # create creator participation
        friendly_game_repository.create_participation(
            db=db,
            friendly_game_id=friendly_game.id,
            club_id=club.id,
            roster_id=roster.id,
            role=FriendlyGameRole.CREATOR
        )

        # Commit everything together
        db.commit()

        return friendly_game, roster

    # if an error occurred, we cancel the transaction.
    except Exception:
        db.rollback()
        raise


async def start_friendly_game(
    db: Session,
    friendly_game_id: int,
    user_id: int,
    requested_state: FriendlyGameState,
) -> int:

    match_id = None

    try:
        # get friendly game
        friendly_game = friendly_game_repository.get_by_id(db,friendly_game_id)

        if friendly_game is None:
            raise FriendlyGameNotFoundError(
                "Friendly game not found"
            )

        # get authenticated user club
        club = club_repository.get_by_user_id(db,user_id)
    
        # we verify that the person wishing to start the match is the creator.
        if (club is None or friendly_game.creator_id != club.id):
            raise FriendlyGameForbiddenError(
                "Only the host can start the friendly game"
            )

        if requested_state != FriendlyGameState.JUGANDO:
            raise FriendlyGameForbiddenError(
                "Invalid state transition"
            )

        # the friendly game must still be waiting to start
        if (friendly_game.state != FriendlyGameState.POR_COMENZAR):
            raise FriendlyGameForbiddenError(
                "Friendly game cannot be started"
            )

        # exactly two participants are required
        if len(friendly_game.participations) != 2:
            raise FriendlyGameForbiddenError(
                "Friendly game must have exactly two participants"
            )

        # identify creator and guest explicitly instead of relying # on database ordering
        creator_participation = None
        guest_participation = None

        for participation in friendly_game.participations:
            if participation.role == FriendlyGameRole.CREATOR:
                creator_participation = participation

            elif participation.role == FriendlyGameRole.GUEST:
                guest_participation = participation

        # verify no repeat role
        if (creator_participation is None or guest_participation is None):
            raise FriendlyGameForbiddenError(
                "Friendly game participants are invalid"
            )

        # create the two runtime MatchParticipations
        match_participation_a = _create_match_participation(
            db=db,
            friendly_participation=creator_participation,
            mirror_position=False,
        )

        match_participation_b = _create_match_participation(
            db=db,
            friendly_participation=guest_participation,
            mirror_position=True,
        )

        # the ball begins at the center of the field and stopped.
        ball = Ball(
            position=(FIELD_WIDTH / 2,FIELD_HEIGHT / 2),
            velocity=(0.0, 0.0),
        )

        # match id is assigned by active_matches.
        match = Match(
            match_id=0,
            participation_a=match_participation_a,
            participation_b=match_participation_b,
            ball=ball,
            duration_ticks=friendly_game.duration * TICS_PER_SECOND,
        )
        # load in memory the behaviors of the 2 clubs
        behaviors = load_match_behaviors(
            db=db,
            match=match,
        )

        friendly_game_repository.update_state(
            db=db,
            friendly_game=friendly_game,
            state=FriendlyGameState.JUGANDO,
        )
        # persist the new state in the database
        db.commit()

        # callback executed when the match finishes
        async def on_finished(
            finished_match: Match,
        ) -> None:
            await _finish_friendly_game(
                friendly_game_id=friendly_game.id,
            )

        try:
            # start the match execution in background
            match_id = start_match(
                match=match,
                behaviors=behaviors,
                on_finished=on_finished,
            )

        except Exception:
            # if the match could not start, restore the previous state
            friendly_game_repository.update_state(
                db=db,
                friendly_game=friendly_game,
                state=FriendlyGameState.POR_COMENZAR,
            )

            db.commit()
            raise

        return match_id

    except Exception:
        # rollback any database changes if an error occurs
        db.rollback()
        raise

async def _finish_friendly_game(
    friendly_game_id: int,
) -> None:
    # sessionlocal because this executes at the final of thew match
    # and the http session maybe expires
    with SessionLocal() as db:
        try:
            friendly_game = friendly_game_repository.get_by_id(
                db,
                friendly_game_id,
            )

            if friendly_game is None:
                return

            friendly_game_repository.update_state(
                db=db,
                friendly_game=friendly_game,
                state=FriendlyGameState.FINALIZADO,
            )

            db.commit()
            # when a match ends, it should no longer appear in the list
            await (session_websocket_service.broadcast_friendly_games(db))

        except Exception:
            db.rollback()
            raise


def join_friendly_game(
    db: Session,
    friendly_game_id: int,
    user_id: int,
    data: FriendlyGameJoin,
):
    try:
        club = club_repository.get_by_user_id(db,user_id)

        friendly_game = friendly_game_repository.get_by_id(
            db,
            friendly_game_id,
        )

        if friendly_game is None:
            raise FriendlyGameNotFound(
                "Friendly game does not exist"
            )

        if friendly_game.state != FriendlyGameState.POR_COMENZAR:
            raise FriendlyGameNotAvailable(
                "Friendly game is not available"
            )

        existing_participation = (
            friendly_game_repository.get_participation_by_club(
                db=db,
                friendly_game_id=friendly_game_id,
                club_id=club.id,
            )
        )

        if existing_participation is not None:
            raise AlreadyParticipating(
                "User is already participating in this friendly game"
            )

        participation_count = (
            friendly_game_repository.count_participations(
                db=db,
                friendly_game_id=friendly_game_id,
            )
        )

        if participation_count >= 2:
            raise FriendlyGameFull(
                "Friendly game is full"
            )

        roster = Roster(
            club_id=club.id,
            formation=data.roster.formation,
        )

        roster.players = [
            PlayerOnRoster(
                player_id=player.player_id,
                is_starter=player.is_starter,
                slot=player.slot,
                initial_behavior_id=player.initial_behavior_id,
            )
            for player in data.roster.players
        ]

        try:
            roster.validate_roster()
        except ValueError as error:
            raise InvalidRoster(str(error))

        for p in data.roster.players:
            player = player_repository.get_by_id(
                db,
                p.player_id,
            )

            if player is None:
                raise InvalidRoster(
                    "Player does not exist"
                )

            if player.club_id != club.id:
                raise InvalidRoster(
                    "Player does not belong to user's club"
                )

            if p.initial_behavior_id is not None:
                behavior = behavior_repository.get_by_id(
                    db,
                    p.initial_behavior_id,
                )

                if behavior is None:
                    raise InvalidRoster(
                        "Behavior does not exist"
                    )

                if not behavior.is_default and behavior.club_id != club.id:
                    raise InvalidRoster(
                        "Behavior does not belong to user's club"
                    )

        roster_repository.save(
            db=db,
            roster=roster,
        )

        participation = (
            friendly_game_repository.create_participation(
                db=db,
                friendly_game_id=friendly_game.id,
                club_id=club.id,
                roster_id=roster.id,
                role=FriendlyGameRole.GUEST,
            )
        )

        db.commit()

        return participation, roster

    except IntegrityError:
        db.rollback()

        raise FriendlyGameNotAvailable(
            "Friendly game is no longer available"
        )

    except Exception:
        db.rollback()
        raise
