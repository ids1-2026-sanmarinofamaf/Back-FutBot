from app.game.constants import (
    FIELD_CENTER,
    FIELD_WIDTH,
    TICS_PER_SECOND,
)
from app.game.types import Position, Side
from app.game.formations import FORMATION_POSITIONS
from app.game.models.ball import Ball
from app.game.models.match import Match
from app.game.models.match_participation import MatchParticipation
from app.game.models.player_in_match import PlayerInMatch
from app.game.default_behaviors import (
    ATTACKER_NAME,
    MIDFIELDER_NAME,
    DEFENDER_NAME,
)

from app.models.roster import Formation
from app.models.player_on_roster import RosterSlot


PREVIEW_DURATION_SECONDS = 30
TEMPORARY_BEHAVIOR_ID = -1
PREVIEW_PLAYER_ID = 2

PLAYER_STATS = 60


def _create_player(
    player_id: int,
    position: Position | None,
    behavior_id: int | None,
) -> PlayerInMatch:
    """
    Create temporary player for behavior preview.
    """
    is_on_field = position is not None
    starting_position = position

    return PlayerInMatch(
        player_id=player_id,
        position=position if position is not None else (0.0, 0.0),
        starting_position=starting_position,
        power=PLAYER_STATS,
        agility=PLAYER_STATS,
        control=PLAYER_STATS,
        speed=PLAYER_STATS,
        strength=PLAYER_STATS,
        current_behavior_id=behavior_id if is_on_field else None,
        is_on_field=is_on_field,
    )


def _create_participation(
    side: Side,
    behavior_ids: tuple[int, int, int],
) -> MatchParticipation:
    """
    Create a temporary participation with three starters
    and three inactive substitutes.
    """
    mirror_position = side == Side.RIGHT
    first_player_id = 1 if side == Side.LEFT else 7
    participation_id = -2 if mirror_position else -1

    slots = (
        RosterSlot.LEFT,
        RosterSlot.CENTER,
        RosterSlot.RIGHT,
    )

    positions = FORMATION_POSITIONS[Formation.DEFENSIVE]

    players = []

    for index, slot in enumerate(slots):
        position = positions[slot]

        if mirror_position:
            position = (
                FIELD_WIDTH - position[0],
                position[1],
            )

        players.append(
            _create_player(
                player_id=first_player_id + index,
                position=position,
                behavior_id=behavior_ids[index]
            )
        )

    for index in range(3, 6):
        players.append(
            _create_player(
                player_id=first_player_id + index,
                position=None,
                behavior_id=None,
            )
        )

    return MatchParticipation(
        club_id=participation_id,
        roster_id=participation_id,
        players=players,
    )


def create_preview_match(
    behavior_teammate_1: int,
    behavior_teammate_2: int,
    default_behaviors_ids: dict[str, int],
) -> Match:
    """
    Create a temporary match for testing a behavior.
    
    Team A:
        LEFT: teammate 1
        CENTER: behavior under test
        RIGHT: teammate 2

    TEAM B:
        LEFT: Defender
        CENTER: Midfielder
        RIGHT: Attacker
    """
    participation_a = _create_participation(
        side=Side.LEFT,
        behavior_ids=(
            behavior_teammate_1,
            TEMPORARY_BEHAVIOR_ID,
            behavior_teammate_2,
        ),
    )

    participation_b = _create_participation(
        side=Side.RIGHT,
        behavior_ids=(
            default_behaviors_ids[DEFENDER_NAME],
            default_behaviors_ids[MIDFIELDER_NAME],
            default_behaviors_ids[ATTACKER_NAME],
        ),
    )

    return Match(
        match_id=0,
        participation_a=participation_a,
        participation_b=participation_b,
        ball = Ball(
            position=FIELD_CENTER,
            velocity=(0.0, 0.0),
        ),
        duration_ticks=PREVIEW_DURATION_SECONDS * TICS_PER_SECOND,
    )
