from sqlalchemy.orm import Session

from app.models.roster import Roster, Formation
from app.models.player_on_roster import PlayerOnRoster
from app.repositories import player_repository

from app.game.models.player_in_match import PlayerInMatch
from app.game.models.match_participation import MatchParticipation
from app.game.formations import FORMATION_POSITIONS
from app.game.constants import FIELD_WIDTH


def _create_player_in_match(
    db: Session,
    player_on_roster: PlayerOnRoster,
    formation: Formation,
    mirror_position: bool,
) -> PlayerInMatch:
    player = player_repository.get_by_id(
        db,
        player_on_roster.player_id,
    )

    if player is None:
        raise ValueError("Player does not exist")

    if not player_on_roster.is_starter:
        starting_position = None
        position = (0.0, 0.0)

    else:
        starting_position = FORMATION_POSITIONS[formation][player_on_roster.slot]

        if mirror_position:
            starting_position = (
                FIELD_WIDTH - starting_position[0],
                starting_position[1],
            )

        position = starting_position

    return PlayerInMatch(
        player_id=player.id,
        position=position,
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


def create_match_participation(
    db: Session,
    roster: Roster,
    mirror_position: bool,
) -> MatchParticipation:
    """
    Build a runtime participation from a persisted roster.
    """
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
        club_id=roster.club_id,
        roster_id=roster.id,
        players=players,
    )
