import pytest

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.api.deps import get_current_user

from app.models.roster import Formation
from app.models.player_on_roster import RosterSlot

from app.services.friendly_game_service import (
    FriendlyGameNotFound,
    FriendlyGameNotAvailable,
    FriendlyGameFull,
    AlreadyParticipating,
    InvalidRoster,
)


client = TestClient(app)

@pytest.fixture
def valid_join_body():
    return {
        "roster": {
            "formation": Formation.OFFENSIVE.value,
            "players": [
                {
                    "player_id": 1,
                    "is_starter": True,
                    "slot": RosterSlot.LEFT.value,
                    "initial_behavior_id": 10,
                },
                {
                    "player_id": 2,
                    "is_starter": True,
                    "slot": RosterSlot.CENTER.value,
                    "initial_behavior_id": 11,
                },
                {
                    "player_id": 3,
                    "is_starter": True,
                    "slot": RosterSlot.RIGHT.value,
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
        }
    }


@pytest.fixture
def fake_db():
    return MagicMock()


@pytest.fixture
def authenticated_client(fake_db):
    fake_user = SimpleNamespace(id=5)

    def override_get_current_user():
        return fake_user

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_current_user] = (
        override_get_current_user
    )

    app.dependency_overrides[get_db] = override_get_db

    yield client

    app.dependency_overrides.clear()

@patch("app.api.friendly_games.join_friendly_game")
def test_join_endpoint_success(
    mock_join,
    authenticated_client,
    fake_db,
    valid_join_body,
):
    participation = MagicMock()
    participation.id = 40

    roster = MagicMock()
    roster.id = 20

    mock_join.return_value = (
        participation,
        roster,
    )

    response = authenticated_client.post(
        "/friendly_games/30/users",
        json=valid_join_body,
    )

    assert response.status_code == 201

    assert response.json() == {
        "friendly_game_id": 30,
        "participation_id": 40,
        "roster_id": 20,
    }

    kwargs = mock_join.call_args.kwargs

    assert kwargs["db"] is fake_db
    assert kwargs["friendly_game_id"] == 30
    assert kwargs["user_id"] == 5

    assert (
        kwargs["data"].roster.formation
        == Formation.OFFENSIVE
    )

@patch("app.api.friendly_games.join_friendly_game")
def test_join_without_token_returns_401(
    mock_join,
    valid_join_body,
):
    app.dependency_overrides.clear()

    response = client.post(
        "/friendly_games/30/users",
        json=valid_join_body,
    )

    assert response.status_code == 401
    mock_join.assert_not_called()

@pytest.mark.parametrize(
    "exception,expected_status",
    [
        (
            FriendlyGameNotFound("Friendly game does not exist"),404),
        (
            FriendlyGameNotAvailable("Friendly game is not available"),409),
        (
            FriendlyGameFull("Friendly game is full"),409),
        (
            AlreadyParticipating("Already participating"),409),
        (
            InvalidRoster("Invalid roster"),400),
    ],
)
@patch("app.api.friendly_games.join_friendly_game")
def test_join_endpoint_maps_service_errors(
    mock_join,
    authenticated_client,
    valid_join_body,
    exception,
    expected_status,
):
    mock_join.side_effect = exception

    response = authenticated_client.post(
        "/friendly_games/30/users",
        json=valid_join_body,
    )

    assert response.status_code == expected_status

@patch("app.api.friendly_games.join_friendly_game")
def test_join_invalid_body_returns_422(
    mock_join,
    authenticated_client,
):
    response = authenticated_client.post(
        "/friendly_games/30/users",
        json={},
    )

    assert response.status_code == 422

    mock_join.assert_not_called()