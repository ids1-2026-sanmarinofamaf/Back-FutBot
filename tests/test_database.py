import importlib.util
from unittest.mock import MagicMock

import pytest
from dotenv import dotenv_values
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect

import app.database as database
from app.database import engine, get_db
from app.main import app
from conftest import ROOT_DIR


def test_la_app_inicia_con_la_url_del_entorno():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200


def test_falla_con_mensaje_claro_si_falta_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # Evita que se cargue el .env del repo, que sí define la variable
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)

    # Se carga una copia aparte del módulo para no romper el engine que usan los demás tests
    spec = importlib.util.spec_from_file_location("database_sin_url", ROOT_DIR / "app" / "database.py")
    module = importlib.util.module_from_spec(spec)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        spec.loader.exec_module(module)


def test_los_modelos_generan_su_tabla():
    assert inspect(engine).has_table("user_account")


def test_los_tests_usan_una_base_distinta_a_la_de_desarrollo():
    dev_url = dotenv_values(ROOT_DIR / ".env").get("DATABASE_URL")
    assert engine.url.render_as_string(hide_password=False) != dev_url


def test_get_db_cierra_la_sesion_al_terminar_el_request(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)

    test_app = FastAPI()

    @test_app.get("/ok")
    def ok(db=Depends(get_db)):
        return {"ok": True}

    with TestClient(test_app) as client:
        assert client.get("/ok").status_code == 200
    session.close.assert_called_once()


def test_get_db_cierra_la_sesion_aunque_haya_error(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)

    test_app = FastAPI()

    @test_app.get("/falla")
    def falla(db=Depends(get_db)):
        raise ValueError("error en el endpoint")

    with TestClient(test_app, raise_server_exceptions=False) as client:
        assert client.get("/falla").status_code == 500
    session.close.assert_called_once()
