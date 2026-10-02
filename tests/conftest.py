import pytest

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = ROOT_DIR / "tests" / "futbot_test.db"

# Los tests usan una base propia, nunca la de desarrollo.
# Se setea ANTES de importar app.database, que lee DATABASE_URL al importarse
# (load_dotenv no pisa variables que ya están definidas).
# Se puede apuntar a otra base (ej. un Postgres de test) con TEST_DATABASE_URL.
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", f"sqlite:///{TEST_DB_PATH}")

from app.game.models.player_in_match import PlayerInMatch
from app.models.player_on_roster import PlayerOnRoster, RosterSlot
from app.models.roster import Roster
from app.game.formations import Formation


# file for defining fixtures to be used by multiple tests

def make_player(player_id: int, is_on_field: bool) -> PlayerInMatch:
    return PlayerInMatch(
        # if it is a substitute, it has neither a position nor an initial behavior.
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

@pytest.fixture
def valid_roster():
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

from alembic import command
from alembic.config import Config

from app.database import engine


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Crea el esquema con las migraciones de Alembic al inicio y lo borra al final."""
    alembic_cfg = Config(str(ROOT_DIR / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
    yield
    command.downgrade(alembic_cfg, "base")
    engine.dispose()
    TEST_DB_PATH.unlink(missing_ok=True)
