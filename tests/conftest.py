import os
from pathlib import Path

# Test database configuration must happen before importing any app module,
# because app.database reads DATABASE_URL when it is imported.
ROOT_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = ROOT_DIR / "tests" / "futbot_test.db"

os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    f"sqlite:///{TEST_DB_PATH}",
)

import pytest

from alembic import command
from alembic.config import Config
from dataclasses import dataclass, replace

from app.database import engine
from app.game.context import BehaviorContext
from app.game.formations import Formation
from app.game.models.actions import KickAction, MoveAction, WaitAction
from app.game.models.player_in_match import PlayerInMatch
from app.game.models.runtime_behavior import RuntimeBehavior
from app.game.primitives import ball
from app.game.types import Period, Side, Position, Velocity
from app.models.player_on_roster import PlayerOnRoster, RosterSlot
from app.models.roster import Roster


def make_player(player_id: int, is_on_field: bool) -> PlayerInMatch:
    return PlayerInMatch(
        # If it is a substitute, it has neither a starting position
        # nor an initial behavior.
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


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Create the test database schema before tests and remove it afterwards."""
    alembic_cfg = Config(str(ROOT_DIR / "alembic.ini"))

    command.upgrade(alembic_cfg, "head")

    yield

    command.downgrade(alembic_cfg, "base")
    engine.dispose()
    TEST_DB_PATH.unlink(missing_ok=True)


@pytest.fixture
def six_players():
    """Return three starters and three substitutes."""
    return [
        make_player(1, True),
        make_player(2, True),
        make_player(3, True),
        make_player(4, False),
        make_player(5, False),
        make_player(6, False),
    ]


@pytest.fixture
def valid_roster():
    """Return a valid roster with three starters and three substitutes."""
    roster = Roster(
        club_id=1,
        formation=Formation.DEFENSIVE,
    )

    roster.players = [
        PlayerOnRoster(
            player_id=1,
            is_starter=True,
            slot=RosterSlot.LEFT,
            initial_behavior_id=1,
        ),
        PlayerOnRoster(
            player_id=2,
            is_starter=True,
            slot=RosterSlot.CENTER,
            initial_behavior_id=1,
        ),
        PlayerOnRoster(
            player_id=3,
            is_starter=True,
            slot=RosterSlot.RIGHT,
            initial_behavior_id=1,
        ),
        PlayerOnRoster(
            player_id=4,
            is_starter=False,
            slot=None,
            initial_behavior_id=None,
        ),
        PlayerOnRoster(
            player_id=5,
            is_starter=False,
            slot=None,
            initial_behavior_id=None,
        ),
        PlayerOnRoster(
            player_id=6,
            is_starter=False,
            slot=None,
            initial_behavior_id=None,
        ),
    ]

    return roster


@pytest.fixture
def context():
    """Return a valid BehaviorContext for game-related unit tests."""
    return BehaviorContext(
        player=(1, (5.0, 4.0)),
        teammates=[
            (2, (6.0, 4.0)),
            (3, (7.0, 5.0)),
        ],
        opponents=[
            (4, (10.0, 8.0)),
            (5, (11.0, 6.0)),
            (6, (12.0, 4.0)),
        ],
        ball=((7.0, 5.0), (1.0, 0.0)),
        my_team_score=1,
        opponent_score=0,
        starting_position=(3.0, 3.0),
        current_period=Period.FIRST_QUARTER,
        side=Side.LEFT,
        match_time_remaining=120.0,
        period_time_remaining=30.0,
        control_range=0.8,
        tics_until_kick=0,
        max_move_speed=8.0,
        max_kick_force=20.0,
    )


@pytest.fixture
def other_context():
    """Return a second BehaviorContext with different values."""
    return BehaviorContext(
        player=(7, (15.0, 10.0)),
        teammates=[
            (8, (14.0, 9.0)),
            (9, (13.0, 8.0)),
        ],
        opponents=[
            (10, (4.0, 3.0)),
            (11, (5.0, 5.0)),
            (12, (6.0, 7.0)),
        ],
        ball=((12.0, 10.0), (-1.0, 0.5)),
        my_team_score=2,
        opponent_score=1,
        starting_position=(17.0, 10.0),
        current_period=Period.SECOND_QUARTER,
        side=Side.RIGHT,
        match_time_remaining=90.0,
        period_time_remaining=20.0,
        control_range=1.2,
        tics_until_kick=2,
        max_move_speed=9.5,
        max_kick_force=25.0,
    )


@pytest.fixture
def move_behavior():
    """Return a runtime behavior whose play() returns a MoveAction."""
    return RuntimeBehavior(
        id=1,
        play=lambda: MoveAction(
            move_direction=(1.0, 0.0),
            move_speed_factor=1.0,
        ),
    )


@pytest.fixture
def kick_behavior():
    """Return a runtime behavior whose play() returns a KickAction."""
    return RuntimeBehavior(
        id=2,
        play=lambda: KickAction(
            kick_direction=(1.0, 0.0),
            kick_force_factor=1.0,
        ),
    )


@pytest.fixture
def wait_behavior():
    """Return a runtime behavior whose play() returns a WaitAction."""
    return RuntimeBehavior(
        id=3,
        play=lambda: WaitAction(),
    )


@pytest.fixture
def invalid_behavior():
    """Return a runtime behavior whose play() returns a non-action value."""
    return RuntimeBehavior(
        id=4,
        play=lambda: ball(),
    )


@pytest.fixture
def failing_behavior():
    """Return a runtime behavior whose play() raises an exception."""

    def failing_play():
        raise RuntimeError("Behavior execution failed")

    return RuntimeBehavior(
        id=5,
        play=failing_play,
    )


@dataclass(frozen=True)
class PlayerSnapshotStub:
    player_id: int
    position: Position
    velocity: Velocity
    starting_position: Position | None

    power: int
    agility: int
    control: int
    speed: int
    strength: int

    current_behavior_id: int | None
    is_on_field: bool

    kick_cooldown_remaining: int = 0
    forced_wait_remaining: int = 0
    collision_penalty_remaining: int = 0


@dataclass(frozen=True)
class BallSnapshotStub:
    position: Position
    velocity: Velocity


@dataclass(frozen=True)
class MatchSnapshotStub:
    players_a: tuple[PlayerSnapshotStub, ...]
    players_b: tuple[PlayerSnapshotStub, ...]

    ball: BallSnapshotStub

    duration_ticks: int
    current_tick: int

    score_a: int
    score_b: int


@pytest.fixture
def player_a_snapshot():
    return PlayerSnapshotStub(
        player_id=1,
        position=(5.0, 4.0),
        velocity=(0.0, 0.0),
        starting_position=(3.0, 3.0),

        # Total PACSS = 300
        power=80,
        agility=40,
        control=70,
        speed=60,
        strength=50,

        current_behavior_id=1,
        is_on_field=True,

        kick_cooldown_remaining=2,
    )


@pytest.fixture
def player_b_snapshot():
    return PlayerSnapshotStub(
        player_id=7,
        position=(30.0, 10.0),
        velocity=(0.0, 0.0),
        starting_position=(35.0, 10.0),

        # Total PACSS = 300
        power=50,
        agility=70,
        control=60,
        speed=80,
        strength=40,

        current_behavior_id=2,
        is_on_field=True,

        kick_cooldown_remaining=1,
    )


@pytest.fixture
def match_snapshot(
    player_a_snapshot,
    player_b_snapshot,
):
    # Team A starters
    teammate_a_1 = PlayerSnapshotStub(
        player_id=2,
        position=(6.0, 4.0),
        velocity=(0.0, 0.0),
        starting_position=(4.0, 5.0),
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
        current_behavior_id=1,
        is_on_field=True,
    )

    teammate_a_2 = PlayerSnapshotStub(
        player_id=3,
        position=(7.0, 5.0),
        velocity=(0.0, 0.0),
        starting_position=(4.0, 7.0),
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
        current_behavior_id=1,
        is_on_field=True,
    )

    # Team A substitutes
    substitute_a_1 = PlayerSnapshotStub(
        player_id=4,
        position=(0.0, 0.0),
        velocity=(0.0, 0.0),
        starting_position=None,
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
        current_behavior_id=None,
        is_on_field=False,
    )

    substitute_a_2 = PlayerSnapshotStub(
        player_id=5,
        position=(0.0, 0.0),
        velocity=(0.0, 0.0),
        starting_position=None,
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
        current_behavior_id=3,
        is_on_field=False,
    )

    substitute_a_3 = PlayerSnapshotStub(
        player_id=6,
        position=(0.0, 0.0),
        velocity=(0.0, 0.0),
        starting_position=None,
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
        current_behavior_id=None,
        is_on_field=False,
    )

    # Team B starters
    teammate_b_1 = PlayerSnapshotStub(
        player_id=8,
        position=(31.0, 8.0),
        velocity=(0.0, 0.0),
        starting_position=(35.0, 8.0),
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
        current_behavior_id=1,
        is_on_field=True,
    )

    teammate_b_2 = PlayerSnapshotStub(
        player_id=9,
        position=(32.0, 6.0),
        velocity=(0.0, 0.0),
        starting_position=(35.0, 6.0),
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
        current_behavior_id=2,
        is_on_field=True,
    )

    # Team B substitutes
    substitute_b_1 = PlayerSnapshotStub(
        player_id=10,
        position=(0.0, 0.0),
        velocity=(0.0, 0.0),
        starting_position=None,
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
        current_behavior_id=None,
        is_on_field=False,
    )

    substitute_b_2 = PlayerSnapshotStub(
        player_id=11,
        position=(0.0, 0.0),
        velocity=(0.0, 0.0),
        starting_position=None,
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
        current_behavior_id=None,
        is_on_field=False,
    )

    substitute_b_3 = PlayerSnapshotStub(
        player_id=12,
        position=(0.0, 0.0),
        velocity=(0.0, 0.0),
        starting_position=None,
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
        current_behavior_id=None,
        is_on_field=False,
    )

    return MatchSnapshotStub(
        players_a=(
            player_a_snapshot,
            teammate_a_1,
            teammate_a_2,
            substitute_a_1,
            substitute_a_2,
            substitute_a_3,
        ),
        players_b=(
            player_b_snapshot,
            teammate_b_1,
            teammate_b_2,
            substitute_b_1,
            substitute_b_2,
            substitute_b_3,
        ),
        ball=BallSnapshotStub(
            position=(20.0, 10.0),
            velocity=(1.0, 0.0),
        ),
        duration_ticks=1200,
        current_tick=200,
        score_a=2,
        score_b=1,
    )


@pytest.fixture
def penalized_player_a_snapshot(player_a_snapshot):
    return replace(
        player_a_snapshot,
        collision_penalty_remaining=10,
    )


@pytest.fixture
def substitute_player_snapshot():
    return PlayerSnapshotStub(
        player_id=100,
        position=(0.0, 0.0),
        velocity=(0.0, 0.0),
        starting_position=None,
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
        current_behavior_id=None,
        is_on_field=False,
    )
