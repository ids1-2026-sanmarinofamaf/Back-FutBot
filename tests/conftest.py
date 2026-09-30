import os
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
TEST_DB_PATH = ROOT_DIR / "tests" / "futbot_test.db"

# Los tests usan una base propia, nunca la de desarrollo.
# Se setea ANTES de importar app.database, que lee DATABASE_URL al importarse
# (load_dotenv no pisa variables que ya están definidas).
# Se puede apuntar a otra base (ej. un Postgres de test) con TEST_DATABASE_URL.
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", f"sqlite:///{TEST_DB_PATH}")

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
