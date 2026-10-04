from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.database import get_db

from app.services.friendly_game_service import (
    FriendlyGameNotFoundError,
    FriendlyGameForbiddenError,
)


client = TestClient(app)


@pytest.fixture
def authenticated_user():
    user = SimpleNamespace(id=123)

    app.dependency_overrides[get_current_user] = (
        lambda: user
    )

    yield user

    app.dependency_overrides.clear()

@pytest.fixture
def api_dependencies():
    user = SimpleNamespace(id=123)
    db = MagicMock()

    def override_current_user():
        return user

    def override_get_db():
        yield db

    app.dependency_overrides[get_current_user] = (
        override_current_user
    )

    app.dependency_overrides[get_db] = (
        override_get_db
    )

    yield user, db

    app.dependency_overrides.clear()

@patch(
    "app.api.friendly_games.start_friendly_game",
    new_callable=AsyncMock,
)
def test_start_friendly_game_returns_200(
    mock_start_friendly_game,
    api_dependencies,
):
    user, db = api_dependencies

    mock_start_friendly_game.return_value = 50

    response = client.patch(
        "/friendly_games/10",
        json={
            "state": "JUGANDO",
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "match_id": 50,
    }

    mock_start_friendly_game.assert_awaited_once_with(
        db=db,
        friendly_game_id=10,
        user_id=user.id,
        requested_state=mock_start_friendly_game.call_args.kwargs[
            "requested_state"
        ],
    )

@patch(
    "app.api.friendly_games.start_friendly_game",
    new_callable=AsyncMock,
)
def test_start_friendly_game_returns_404_when_not_found(
    mock_start_friendly_game,
    api_dependencies,
):
    mock_start_friendly_game.side_effect = (
        FriendlyGameNotFoundError(
            "Friendly game not found"
        )
    )

    response = client.patch(
        "/friendly_games/999",
        json={
            "state": "JUGANDO",
        },
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Friendly game not found",
    }

@patch(
    "app.api.friendly_games.start_friendly_game",
    new_callable=AsyncMock,
)
def test_start_friendly_game_returns_403_when_forbidden(
    mock_start_friendly_game,
    api_dependencies,
):
    mock_start_friendly_game.side_effect = (
        FriendlyGameForbiddenError(
            "Only the host can start the friendly game"
        )
    )

    response = client.patch(
        "/friendly_games/10",
        json={
            "state": "JUGANDO",
        },
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": "Only the host can start the friendly game",
    }

def test_start_friendly_game_without_token_returns_401():
    app.dependency_overrides.clear()

    response = client.patch(
        "/friendly_games/10",
        json={
            "state": "JUGANDO",
        },
    )

    assert response.status_code == 401

def test_start_friendly_game_invalid_state_returns_422(
    api_dependencies,
):
    response = client.patch(
        "/friendly_games/10",
        json={
            "state": "CUALQUIER_COSA",
        },
    )

    assert response.status_code == 422