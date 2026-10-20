from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash, verify_password
from app.database import SessionLocal
from app.main import app
from app.models.club import Club
from app.models.league import League, LeaguePrivacy, LeagueState
from app.models.user import User
from app.services.league_service import ClubNotFound


client = TestClient(app)

EMAIL = "league@mail.com"
PASSWORD = "secreta123"


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
        club=Club(name="league-club"),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    yield user

    db.rollback()
    db.query(League).delete()
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
        "name": "Liga1",
        "match_duration": 10,
        "max_clubs": 8,
        "privacy": "PUBLICA",
        "password": "",
    }


def count_leagues(db):
    db.expire_all()
    return db.query(League).count()


# a valid body creates the league with the same values and returns 201 with its id
def test_create_league_success(user, db):
    response = client.post(
        "/leagues",
        json=valid_body(),
        headers=auth_header(login()),
    )

    assert response.status_code == 201
    league_id = response.json()["league_id"]

    league = db.get(League, league_id)
    assert league is not None
    assert league.name == "Liga1"
    assert league.match_duration == 10
    assert league.max_clubs == 8
    assert league.privacy == LeaguePrivacy.PUBLICA
    assert league.password_hash is None
    assert league.state == LeagueState.POR_COMENZAR
    # the league belongs to the club of the user that made the request
    assert league.creator_id == user.club.id


# a private league stores the hashed password, never the plain one
def test_create_private_league_hashes_password(user, db):
    body = valid_body()
    body["privacy"] = "PRIVADA"
    body["password"] = "clave123"

    response = client.post(
        "/leagues",
        json=body,
        headers=auth_header(login()),
    )

    assert response.status_code == 201

    league = db.get(League, response.json()["league_id"])
    assert league.privacy == LeaguePrivacy.PRIVADA
    assert league.password_hash != "clave123"
    assert verify_password("clave123", league.password_hash)


# a body missing any required field returns 400 and does not create the league
@pytest.mark.parametrize("missing_field", ["name", "match_duration", "max_clubs", "privacy"])
def test_create_league_missing_field_returns_400(user, db, missing_field):
    body = valid_body()
    del body[missing_field]

    response = client.post(
        "/leagues",
        json=body,
        headers=auth_header(login()),
    )

    assert response.status_code == 400
    assert count_leagues(db) == 0


# an empty name returns 400
def test_create_league_empty_name_returns_400(user, db):
    body = valid_body()
    body["name"] = ""

    response = client.post(
        "/leagues",
        json=body,
        headers=auth_header(login()),
    )

    assert response.status_code == 400
    assert count_leagues(db) == 0


# a private league without password returns 400
def test_create_private_league_without_password_returns_400(user, db):
    body = valid_body()
    body["privacy"] = "PRIVADA"
    body["password"] = ""

    response = client.post(
        "/leagues",
        json=body,
        headers=auth_header(login()),
    )

    assert response.status_code == 400
    assert count_leagues(db) == 0


# a public league with a password returns 400
def test_create_public_league_with_password_returns_400(user, db):
    body = valid_body()
    body["password"] = "clave123"

    response = client.post(
        "/leagues",
        json=body,
        headers=auth_header(login()),
    )

    assert response.status_code == 400
    assert count_leagues(db) == 0


# a request without token returns 401
def test_create_league_without_token_returns_401(user, db):
    response = client.post("/leagues", json=valid_body())

    assert response.status_code == 401
    assert count_leagues(db) == 0


# a user without club returns 404
def test_create_league_without_club_returns_404(user, db):
    with patch("app.api.leagues.create_league", side_effect=ClubNotFound("Club does not exist")):
        response = client.post(
            "/leagues",
            json=valid_body(),
            headers=auth_header(login()),
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Club does not exist"}
