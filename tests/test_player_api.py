from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import get_password_hash
from app.database import SessionLocal, engine
from app.main import app
from app.models.club import Club
from app.models.player import Player
from app.models.user import User


client = TestClient(app)

EMAIL = "players@mail.com"
PASSWORD = "secreta123"
OTHER_EMAIL = "other-players@mail.com"


@pytest.fixture(autouse=True)
def players_table():
    # TODO: remove once the players migration exists; then alembic creates the table
    Player.__table__.create(engine, checkfirst=True)
    yield
    Player.__table__.drop(engine, checkfirst=True)


@pytest.fixture
def db():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def user(db):
    user = User(
        email=EMAIL,
        hash_passwd=get_password_hash(PASSWORD),
        club=Club(name="players-club"),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    yield user

    db.query(Player).delete()
    db.query(Club).delete()
    db.query(User).delete()
    db.commit()


def login():
    response = client.post(
        "/sessions",
        json={
            "email": EMAIL,
            "password": PASSWORD,
        },
    )

    return response.json()["token"]


def auth_header(token):
    return {
        "Authorization": f"Bearer {token}"
    }


def valid_body():
    return {
        "name": "Bot",
        "power": 60,
        "agility": 60,
        "control": 60,
        "speed": 60,
        "strength": 60,
    }


def test_create_player_without_token_returns_401():
    response = client.post("/clubes/me/players", json=valid_body())

    assert response.status_code == 401


def test_create_player_with_invalid_token_returns_401():
    response = client.post(
        "/clubes/me/players",
        json=valid_body(),
        headers=auth_header("invalid.token.value"),
    )

    assert response.status_code == 401


def test_create_player_success_persists_and_can_be_retrieved(user, db):
    token = login()

    response = client.post(
        "/clubes/me/players",
        json=valid_body(),
        headers=auth_header(token),
    )

    assert response.status_code == 201
    player_id = response.json()["id_jugador"]

    # the player is stored with all its data and linked to the user's club
    player = db.get(Player, player_id)
    assert player is not None
    assert player.club_id == user.club.id
    assert player.name == "Bot"
    assert player.power == 60

    # and the frontend can retrieve it through the endpoint
    response = client.get(
        f"/clubes/me/players/{player_id}",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json() == {"id": player_id, **valid_body()}


@pytest.mark.parametrize(
    "changes",
    [
        {"power": 19},                                  # below minimum
        {"speed": 101},                                 # above maximum
        {"name": ""},                                   # empty name
        {"power": 100, "agility": 100, "control": 41},  # total stats above 300
    ],
)
def test_create_player_with_invalid_data_is_rejected(user, db, changes):
    token = login()

    response = client.post(
        "/clubes/me/players",
        json={**valid_body(), **changes},
        headers=auth_header(token),
    )

    assert response.status_code == 422
    assert db.query(Player).count() == 0


def test_create_player_with_missing_field_is_rejected(user, db):
    token = login()

    body = valid_body()
    body.pop("strength")

    response = client.post(
        "/clubes/me/players",
        json=body,
        headers=auth_header(token),
    )

    assert response.status_code == 422
    assert db.query(Player).count() == 0


@patch("app.services.player_service.player_repository.save")
def test_create_player_persistence_error_returns_500(mock_save, user, db):
    token = login()

    mock_save.side_effect = SQLAlchemyError("db down")

    response = client.post(
        "/clubes/me/players",
        json=valid_body(),
        headers=auth_header(token),
    )

    assert response.status_code == 500
    assert db.query(Player).count() == 0


def test_get_player_not_found_returns_404(user):
    token = login()

    response = client.get(
        "/clubes/me/players/9999",
        headers=auth_header(token),
    )

    assert response.status_code == 404


def test_get_player_from_another_club_returns_404(user, db):
    other_user = User(
        email=OTHER_EMAIL,
        hash_passwd=get_password_hash(PASSWORD),
        club=Club(name="other-club"),
    )
    db.add(other_user)
    db.commit()

    other_player = Player(club_id=other_user.club.id, **valid_body())
    db.add(other_player)
    db.commit()

    token = login()

    response = client.get(
        f"/clubes/me/players/{other_player.id}",
        headers=auth_header(token),
    )

    assert response.status_code == 404
