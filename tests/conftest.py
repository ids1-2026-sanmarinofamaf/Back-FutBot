import pytest

from app.game.models.player_in_match import PlayerInMatch
from app.game.types import Position, Velocity

# file for defining fixtures to be used by multiple tests

def make_player(player_id: int, is_on_field: bool) -> PlayerInMatch:
    return PlayerInMatch(
        player_id=player_id,
        position=(0.0, 0.0),
        velocity=(0.0, 0.0),
        starting_position=(8.0, 5.0) if is_on_field else None,
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
        current_behavior_id=1 if is_on_field else None,
        is_on_field=is_on_field,
    )


@pytest.fixture
def six_players():      # 3 starters and 3 substitutes
    return [
        make_player(1, True),
        make_player(2, True),
        make_player(3, True),
        make_player(4, False),
        make_player(5, False),
        make_player(6, False),
    ]