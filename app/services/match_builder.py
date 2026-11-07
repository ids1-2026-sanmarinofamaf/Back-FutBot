from sqlalchemy.orm import Session

from app.models.roster import Roster, Formation
from app.models.player_on_roster import PlayerOnRoster
from app.repositories import player_repository, club_repository, behavior_repository

from app.game.models.player_in_match import PlayerInMatch
from app.game.models.match_participation import MatchParticipation
from app.game.formations import FORMATION_POSITIONS
from app.game.constants import FIELD_WIDTH


def _create_player_in_match(
    db: Session,
    player_on_roster: PlayerOnRoster,
    formation: Formation,
    mirror_position: bool,
    shirt_number: int = 1,
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
        if player_on_roster.slot is None:
            raise ValueError("Starter player must have a slot assigned")

        base_position = FORMATION_POSITIONS[formation][player_on_roster.slot]

        if mirror_position:
            starting_position = (
                FIELD_WIDTH - base_position[0],
                base_position[1],
            )
        else:
            starting_position = base_position

        position = starting_position

    current_behavior_id = (
        player_on_roster.initial_behavior_id
        if player_on_roster.is_starter
        else None
    )
    current_behavior_name: str | None = None
    if current_behavior_id is not None:
        behavior = behavior_repository.get_by_id(db, current_behavior_id)
        if behavior is not None:
            current_behavior_name = behavior.name

    player_name = str(getattr(player, "name", "") or "")

    return PlayerInMatch(
        player_id=player.id,
        position=position,
        starting_position=starting_position,
        power=player.power,
        agility=player.agility,
        control=player.control,
        speed=player.speed,
        strength=player.strength,
        current_behavior_id=current_behavior_id,
        is_on_field=player_on_roster.is_starter,
        name=player_name,
        shirt_number=shirt_number,
        current_behavior_name=current_behavior_name,
    )


def create_match_participation(
    db: Session,
    roster: Roster,
    mirror_position: bool,
) -> MatchParticipation:
    """
    Build a runtime participation from a persisted roster.
    """
    # assign number to players
    players = [
        _create_player_in_match(
            db=db,
            player_on_roster=player_on_roster,
            formation=roster.formation,
            mirror_position=mirror_position,
            shirt_number=i,
        )
        for i, player_on_roster in enumerate(
            roster.players, start=1
        )
    ]

    club = club_repository.get_by_id(
        db,
        roster.club_id,
    )

    if club is None:
        raise ValueError("Club does not exist")

    return MatchParticipation(
        club_id=roster.club_id,
        roster_id=roster.id,
        club_name=club.name,
        players=players,
        coach_behavior_id=roster.coach_behavior_id,
    )
