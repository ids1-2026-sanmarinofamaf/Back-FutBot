from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.database import SessionLocal
from app.main import app
from app.models.club import Club
from app.models.user import User


client = TestClient(app)

EMAIL = "friendly@mail.com"
PASSWORD = "secreta123"


@pytest.fixture
def user():
    db = SessionLocal()

    user = User(
        email=EMAIL,
        hash_passwd=get_password_hash(PASSWORD),
        club=Club(name="friendly-club"),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    yield user

    db.query(Club).delete()
    db.query(User).delete()
    db.commit()
    db.close()


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
        "duration": 1000,
        "roster": {
            "formation": "offensive",
            "players": [
                {
                    "player_id": 1,
                    "is_starter": True,
                    "slot": "left",
                    "initial_behavior_id": 10,
                },
                {
                    "player_id": 2,
                    "is_starter": True,
                    "slot": "center",
                    "initial_behavior_id": 11,
                },
                {
                    "player_id": 3,
                    "is_starter": True,
                    "slot": "right",
                    "initial_behavior_id": 12,
                },
                {
                    "player_id": 4,
                    "is_starter": False,
                    "slot": None,
                    "initial_behavior_id": None,
                },
                {
                    "player_id": 5,
                    "is_starter": False,
                    "slot": None,
                    "initial_behavior_id": None,
                },
                {
                    "player_id": 6,
                    "is_starter": False,
                    "slot": None,
                    "initial_behavior_id": None,
                },
            ],
        },
    }

def test_create_friendly_game_without_token_returns_401():
    response = client.post(
        "/friendly_games",
        json=valid_body(),
    )

    assert response.status_code == 401

def test_create_friendly_game_with_incomplete_roster_returns_400(user):
    token = login()

    body = valid_body()
    body["roster"]["players"].pop()

    response = client.post(
        "/friendly_games",
        json=body,
        headers=auth_header(token),
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "A roster must have exactly 6 players"
    )

@patch("app.services.friendly_game_service.player_repository")
@patch("app.services.friendly_game_service.behavior_repository")
def test_create_friendly_game_success_returns_201(
    mock_behavior_repository,
    mock_player_repository,
    user,
):
    token = login()

    club_id = user.club.id

    player = MagicMock()
    player.club_id = club_id
    mock_player_repository.get_by_id.return_value = player

    behavior = MagicMock()
    behavior.club_id = club_id
    mock_behavior_repository.get_by_id.return_value = behavior

    response = client.post(
        "/friendly_games",
        json=valid_body(),
        headers=auth_header(token),
    )

    assert response.status_code == 201

    data = response.json()

    assert "friendly_game_id" in data

def test_create_friendly_game_with_zero_duration_is_rejected(user):
    token = login()

    body = valid_body()
    body["duration"] = 0

    response = client.post(
        "/friendly_games",
        json=body,
        headers=auth_header(token),
    )

    assert response.status_code == 422