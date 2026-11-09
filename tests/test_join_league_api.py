from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.leagues import get_current_user
from app.main import app
from app.services.league_service import (
    AlreadyParticipating,
    InvalidLeaguePassword,
    InvalidRoster,
    LeagueFull,
    LeagueNotAvailable,
    LeagueNotFound,
)


client = TestClient(app)
LEAGUE_ID = 10
USER_ID = 20
CLUB_ID = 30
ROSTER_ID = 40
JOIN_URL = f"/leagues/{LEAGUE_ID}/users"


def fake_current_user():
    """Usuario autenticado ficticio, sin consultar la base de datos."""
    return SimpleNamespace(id=USER_ID)


@pytest.fixture
def authenticated_client():
    app.dependency_overrides[get_current_user] = fake_current_user
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def valid_join_payload():
    slots = ["left", "center", "right"]
    return {
        "roster": {
            "formation": "defensive",
            "players": [
                {
                    "player_id": i + 1,
                    "is_starter": i < 3,
                    "slot": slots[i] if i < 3 else None,
                    "initial_behavior_id": 1 if i < 3 else None,
                }
                for i in range(6)
            ],
        },
        "password": None,
    }


def test_join_league_without_token_returns_401(valid_join_payload):
    response = client.post(JOIN_URL, json=valid_join_payload)
    assert response.status_code == 401


def test_join_league_with_invalid_token_returns_401(valid_join_payload):
    response = client.post(
        JOIN_URL,
        headers={"Authorization": "Bearer invalid.token.value"},
        json=valid_join_payload,
    )
    assert response.status_code == 401


def test_join_league_success_returns_200(
    authenticated_client,
    valid_join_payload,
):
    participation = SimpleNamespace(club_id=CLUB_ID)
    roster = SimpleNamespace(id=ROSTER_ID)

    with patch(
        "app.api.leagues.join_league", return_value=(participation, roster)
    ) as mock_join:
        response = authenticated_client.post(JOIN_URL, json=valid_join_payload)

    assert response.status_code == 200
    assert response.json() == {
        "league_id": LEAGUE_ID,
        "club_id": CLUB_ID,
        "roster_id": ROSTER_ID,
    }
    mock_join.assert_called_once()
    assert mock_join.call_args.kwargs["league_id"] == LEAGUE_ID
    assert mock_join.call_args.kwargs["user_id"] == USER_ID


def test_join_league_already_participating_returns_409(
    authenticated_client,
    valid_join_payload,
):
    with patch(
        "app.api.leagues.join_league",
        side_effect=AlreadyParticipating("Club is already participating in this league"),
    ):
        response = authenticated_client.post(JOIN_URL, json=valid_join_payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "Club is already participating in this league"


def test_join_league_not_found_returns_404(
    authenticated_client,
    valid_join_payload
):
    with patch(
        "app.api.leagues.join_league",
        side_effect=LeagueNotFound("League does not exist"),
    ):
        response = authenticated_client.post(JOIN_URL, json=valid_join_payload)

    assert response.status_code == 404
    assert response.json()["detail"] == "League does not exist"


def test_join_private_league_without_password_returns_403(
    authenticated_client,
    valid_join_payload,
):
    with patch(
        "app.api.leagues.join_league",
        side_effect=InvalidLeaguePassword("This league is private"),
    ):
        response = authenticated_client.post(JOIN_URL, json=valid_join_payload)

    assert response.status_code == 403
    assert response.json()["detail"] == "This league is private"


def test_join_private_league_with_wrong_password_returns_403(
    authenticated_client,
    valid_join_payload,
):
    valid_join_payload["password"] = "wrongpassword"
    with patch(
        "app.api.leagues.join_league",
        side_effect=InvalidLeaguePassword("Incorrect password"),
    ):
        response = authenticated_client.post(JOIN_URL, json=valid_join_payload)

    assert response.status_code == 403
    assert response.json()["detail"] == "Incorrect password"


def test_join_private_league_with_correct_password_returns_200(
    authenticated_client,
    valid_join_payload,
):
    valid_join_payload["password"] = "secret123"
    participation = SimpleNamespace(club_id=CLUB_ID)
    roster = SimpleNamespace(id=ROSTER_ID)

    with patch(
        "app.api.leagues.join_league", return_value=(participation, roster)
    ) as mock_join:
        response = authenticated_client.post(JOIN_URL, json=valid_join_payload)

    assert response.status_code == 200
    assert response.json()["roster_id"] == ROSTER_ID
    assert mock_join.call_args.kwargs["data"].password == "secret123"


def test_join_league_in_progress_returns_409(
    authenticated_client,
    valid_join_payload
):
    with patch(
        "app.api.leagues.join_league",
        side_effect=LeagueNotAvailable("League is not available"),
    ):
        response = authenticated_client.post(JOIN_URL, json=valid_join_payload)

    assert response.status_code == 409
    assert response.json()["detail"] == "League is not available"


def test_join_full_league_returns_403(
    authenticated_client,
    valid_join_payload,
):
    with patch(
        "app.api.leagues.join_league",
        side_effect=LeagueFull("League is full"),
    ):
        response = authenticated_client.post(JOIN_URL, json=valid_join_payload)

    assert response.status_code == 403
    assert response.json()["detail"] == "League is full"


def test_join_league_invalid_roster_returns_400(
    authenticated_client,
    valid_join_payload,
):
    with patch(
        "app.api.leagues.join_league",
        side_effect=InvalidRoster("Invalid roster"),
    ):
        response = authenticated_client.post(JOIN_URL, json=valid_join_payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid roster"


def test_join_league_invalid_payload_returns_422(authenticated_client):
    with patch("app.api.leagues.join_league") as mock_join:
        response = authenticated_client.post(
            JOIN_URL,
            json={"roster": {"formation": "invalid", "players": []}},
        )

    assert response.status_code == 422
    mock_join.assert_not_called()


def test_join_league_success_broadcasts_leagues(
    authenticated_client,
    valid_join_payload,
):
    participation = SimpleNamespace(club_id=CLUB_ID)
    roster = SimpleNamespace(id=ROSTER_ID)

    with (
        patch(
            "app.api.leagues.join_league",
            return_value=(participation, roster),
        ) as mock_join,
        patch(
            "app.api.leagues.session_websocket_service.broadcast_leagues",
            new_callable=AsyncMock,
        ) as mock_broadcast,
    ):
        response = authenticated_client.post(
            JOIN_URL,
            json=valid_join_payload,
        )

    assert response.status_code == 200
    mock_join.assert_called_once()
    mock_broadcast.assert_awaited_once()

    # El broadcast debe recibir la misma sesión que join_league.
    assert (
        mock_broadcast.call_args.args[0]
        is mock_join.call_args.kwargs["db"]
    )


def test_join_league_failure_does_not_broadcast(
    authenticated_client,
    valid_join_payload,
):
    with (
        patch(
            "app.api.leagues.join_league",
            side_effect=AlreadyParticipating(
                "Club is already participating in this league"
            ),
        ),
        patch(
            "app.api.leagues.session_websocket_service.broadcast_leagues",
            new_callable=AsyncMock,
        ) as mock_broadcast,
    ):
        response = authenticated_client.post(
            JOIN_URL,
            json=valid_join_payload,
        )

    assert response.status_code == 409
    mock_broadcast.assert_not_awaited()
