from sqlalchemy.orm import Session

from app.models.roster import Roster
from app.models.player_on_roster import PlayerOnRoster

from app.schemas.friendly_game import FriendlyGameCreate
from app.models.friendly_game_participation import FriendlyGameRole
from app.repositories import (
    friendly_game_repository,
    roster_repository,
    player_repository,
    behavior_repository,
    club_repository
)


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

                if behavior.club_id != club.id:
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