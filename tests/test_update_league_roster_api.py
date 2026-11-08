from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.leagues import get_current_user
from app.database import get_db
from app.main import app
from app.schemas.roster import RosterDetail
from app.services.league_service import (
    InvalidLeagueState,
    InvalidRoster,
    LeagueForbidden,
    LeagueNotFound,
)


client = TestClient(app)

LEAGUE_ID = 10
USER_ID = 20
ROSTER_ID = 30

URL = f"/leagues/{LEAGUE_ID}/users/me/roster"


@pytest.fixture
def authenticated_client():
    app.dependency_overrides[get_current_user] = (
        lambda: SimpleNamespace(id=USER_ID)
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()

    yield client

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def roster_payload():
    slots = ["left", "center", "right"]

    return {
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
    }


# PUT successful update
def test_put_success_returns_200(
    authenticated_client,
    roster_payload,
):
    roster_payload["coach_behavior_id"] = 7
    with patch("app.api.leagues.update_league_roster") as mock_update:
        response = authenticated_client.put(
            URL,
            json=roster_payload,
        )

    assert response.status_code == 200
    assert response.json() == {"message": "Roster updated successfully"}

    mock_update.assert_called_once()

    kwargs = mock_update.call_args.kwargs

    assert kwargs["league_id"] == LEAGUE_ID
    assert kwargs["user_id"] == USER_ID
    assert kwargs["data"].formation.value == "defensive"
    assert kwargs["data"].coach_behavior_id == 7
    assert len(kwargs["data"].players) == 6


# GET successful 
def test_get_success_returns_roster(
    authenticated_client,
    roster_payload,
):
    roster = RosterDetail(
        roster_id=ROSTER_ID,
        **roster_payload,
    )

    with patch(
        "app.api.leagues.get_league_roster",
        return_value=roster,
    ) as mock_get:
        response = authenticated_client.get(URL)

    assert response.status_code == 200

    assert response.json() == {
        "roster_id": ROSTER_ID,
        **roster_payload,
        "coach_behavior_id": None,
    }

    mock_get.assert_called_once()

    assert mock_get.call_args.kwargs["league_id"] == LEAGUE_ID
    assert mock_get.call_args.kwargs["user_id"] == USER_ID


# missing token
@pytest.mark.parametrize("method", ["get", "put"])
def test_without_token_returns_401(
    method,
    roster_payload,
):
    request = getattr(client, method)

    kwargs = (
        {"json": roster_payload}
        if method == "put"
        else {}
    )

    response = request(URL, **kwargs)

    assert response.status_code == 401


# invalid token
@pytest.mark.parametrize("method", ["get", "put"])
def test_invalid_token_returns_401(
    method,
    roster_payload,
):
    request = getattr(client, method)

    kwargs = (
        {"json": roster_payload}
        if method == "put"
        else {}
    )

    response = request(
        URL,
        headers={"Authorization": "Bearer invalid.token.value"},
        **kwargs,
    )

    assert response.status_code == 401


# league does not exist (get and put)
@pytest.mark.parametrize(
    "method,service_name",
    [
        ("get", "get_league_roster"),
        ("put", "update_league_roster"),
    ],
)
def test_league_not_found_returns_404(
    authenticated_client,
    roster_payload,
    method,
    service_name,
):
    with patch(
        f"app.api.leagues.{service_name}",
        side_effect=LeagueNotFound("League does not exist"),
    ):
        kwargs = (
            {"json": roster_payload}
            if method == "put"
            else {}
        )

        response = getattr(
            authenticated_client,
            method,
        )(URL, **kwargs)

    assert response.status_code == 404
    assert response.json()["detail"] == "League does not exist"


# user does not participate in league (get and put)
@pytest.mark.parametrize(
    "method,service_name",
    [
        ("get", "get_league_roster"),
        ("put", "update_league_roster"),
    ],
)
def test_nonparticipant_returns_403(
    authenticated_client,
    roster_payload,
    method,
    service_name,
):
    with patch(
        f"app.api.leagues.{service_name}",
        side_effect=LeagueForbidden(
            "User is not participating in this league"
        ),
    ):
        kwargs = (
            {"json": roster_payload}
            if method == "put"
            else {}
        )

        response = getattr(
            authenticated_client,
            method,
        )(URL, **kwargs)

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "User is not participating in this league"
    )


# invalid roster (put)
def test_put_invalid_roster_returns_400(
    authenticated_client,
    roster_payload,
):
    with patch(
        "app.api.leagues.update_league_roster",
        side_effect=InvalidRoster(
            "A roster cannot contain duplicate players"
        ),
    ):
        response = authenticated_client.put(
            URL,
            json=roster_payload,
        )

    assert response.status_code == 400
    assert "duplicate" in response.json()["detail"]


# league is not in progress (put)
def test_put_inactive_league_returns_409(
    authenticated_client,
    roster_payload,
):
    with patch(
        "app.api.leagues.update_league_roster",
        side_effect=InvalidLeagueState(
            "League is not in progress"
        ),
    ):
        response = authenticated_client.put(
            URL,
            json=roster_payload,
        )

    assert response.status_code == 409

    assert response.json()["detail"] == (
        "League is not in progress"
    )


# invalid request body (put)
@pytest.mark.parametrize(
    "invalid_payload",
    [
        {},
        {
            "formation": "invalid",
            "players": [],
        },
        {
            "formation": "defensive",
            "players": "invalid",
        },
        {
            "formation": "defensive",
            "players": [
                {
                    "player_id": "abc",
                    "is_starter": True,
                }
            ],
        },
    ],
)

def test_put_invalid_schema_returns_422(
    authenticated_client,
    invalid_payload,
):
    with patch("app.api.leagues.update_league_roster") as mock_update:
        response = authenticated_client.put(
            URL,
            json=invalid_payload,
        )

    assert response.status_code == 422
    mock_update.assert_not_called()

def test_put_invalid_coach_behavior_returns_400(
    authenticated_client,
    roster_payload,
):
    roster_payload["coach_behavior_id"] = 999

    with patch(
        "app.api.leagues.update_league_roster",
        side_effect=InvalidRoster(
            "Coach behavior doesn't exist."
        ),
    ):
        response = authenticated_client.put(
            URL,
            json=roster_payload,
        )

    assert response.status_code == 400
    assert response.json()["detail"] == ("Coach behavior doesn't exist.")