import pytest

from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.api.matches import get_current_user, change_player_behavior
from app.database import get_db


client = TestClient(app)

USER_ID = 1
MATCH_ID = 100
PLAYER_ID = 10
BEHAVIOR_ID = 7

URL = f"/live_match/{MATCH_ID}/me/{PLAYER_ID}/behavior"


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
def valid_payload():
    return {"behavior_id": BEHAVIOR_ID}


def test_change_behavior_success_returns_204(
    authenticated_client,
    valid_payload,
):
    with patch(
        "app.api.matches.change_player_behavior"
    ) as mock_change:
        response = authenticated_client.put(
            URL,
            json=valid_payload,
        )

    assert response.status_code == 204
    assert response.content == b""

    mock_change.assert_called_once()

    kwargs = mock_change.call_args.kwargs

    assert kwargs["user_id"] == USER_ID
    assert kwargs["match_id"] == MATCH_ID
    assert kwargs["player_id"] == PLAYER_ID
    assert kwargs["behavior_id"] == BEHAVIOR_ID


def test_change_behavior_without_token_returns_401():
    response = client.put(
        URL,
        json={"behavior_id": BEHAVIOR_ID},
    )

    assert response.status_code == 401


def test_change_behavior_invalid_token_returns_401():
    response = client.put(
        URL,
        headers={
            "Authorization": "Bearer invalid.token.value"
        },
        json={"behavior_id": BEHAVIOR_ID},
    )

    assert response.status_code == 401


def test_change_behavior_user_not_participating_returns_403(
    authenticated_client,
    valid_payload,
):
    with patch(
        "app.api.matches.change_player_behavior",
        side_effect=PermissionError(
            "User is not participating in this match"
        ),
    ):
        response = authenticated_client.put(
            URL,
            json=valid_payload,
        )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "User is not participating in this match"
    )


@pytest.mark.parametrize(
    "error_message",
    [
        "Match not found",
        "Player not found in user's team",
        "Behavior not found or unavailable",
    ],
)
def test_change_behavior_not_found_returns_404(
    authenticated_client,
    valid_payload,
    error_message,
):
    with patch(
        "app.api.matches.change_player_behavior",
        side_effect=LookupError(error_message),
    ):
        response = authenticated_client.put(
            URL,
            json=valid_payload,
        )

    assert response.status_code == 404
    assert response.json()["detail"] == error_message


@pytest.mark.parametrize(
    "error_message",
    [
        "Match is not in progress",
        "Player is not on the field",
    ],
)
def test_change_behavior_bad_request_returns_400(
    authenticated_client,
    valid_payload,
    error_message,
):
    with patch(
        "app.api.matches.change_player_behavior",
        side_effect=ValueError(error_message),
    ):
        response = authenticated_client.put(
            URL,
            json=valid_payload,
        )

    assert response.status_code == 400
    assert response.json()["detail"] == error_message


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {},
        {"behavior_id": None},
        {"behavior_id": "invalid"},
        {"behavior_id": 0},
        {"behavior_id": -1},
        {"new_behaviour": 7},
        [],
        "invalid",
    ],
)
def test_change_behavior_invalid_body_returns_422(
    authenticated_client,
    invalid_payload,
):
    with patch(
        "app.api.matches.change_player_behavior"
    ) as mock_change:
        response = authenticated_client.put(
            URL,
            json=invalid_payload,
        )

    assert response.status_code == 422
    mock_change.assert_not_called()
