import importlib.util
from unittest.mock import MagicMock

import pytest
from dotenv import dotenv_values
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect

import app.database as database
from app.database import engine, get_db, SessionLocal
from app.main import app
from conftest import ROOT_DIR
from app.models.behavior import Behavior


def test_app_starts_with_database_url_from_env():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200


def test_fails_with_clear_message_when_database_url_is_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # Prevent loading the repo's .env, which does define the variable
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)

    # Load a separate copy of the module so the engine used by other tests is not replaced
    spec = importlib.util.spec_from_file_location("database_without_url", ROOT_DIR / "app" / "database.py")
    module = importlib.util.module_from_spec(spec)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        spec.loader.exec_module(module)


def test_models_create_their_table():
    assert inspect(engine).has_table("user_account")


def test_tests_use_a_different_database_than_development():
    dev_url = dotenv_values(ROOT_DIR / ".env").get("DATABASE_URL")
    assert engine.url.render_as_string(hide_password=False) != dev_url


def test_get_db_closes_session_after_request(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)

    test_app = FastAPI()

    @test_app.get("/ok")
    def ok(db=Depends(get_db)):
        return {"ok": True}

    with TestClient(test_app) as client:
        assert client.get("/ok").status_code == 200
    session.close.assert_called_once()


def test_get_db_closes_session_even_on_error(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)

    test_app = FastAPI()

    @test_app.get("/fail")
    def fail(db=Depends(get_db)):
        raise ValueError("endpoint error")

    with TestClient(test_app, raise_server_exceptions=False) as client:
        assert client.get("/fail").status_code == 500
    session.close.assert_called_once()


def test_default_behaviors_are_seeded():
    with SessionLocal() as session:
        behaviors = (
            session.query(Behavior)
            .filter(Behavior.is_default.is_(True))
            .all()
        )

        assert len(behaviors) == 3

        assert {behavior.name for behavior in behaviors} == {
            "Attacker",
            "Midfielder",
            "Defender",
        }

        assert all(behavior.club_id is None for behavior in behaviors)


def test_seeded_default_behaviors_have_code():
    with SessionLocal() as session:
        behaviors = (
            session.query(Behavior)
            .filter(Behavior.is_default.is_(True))
            .all()
        )

        assert all(behavior.code.strip() for behavior in behaviors)
