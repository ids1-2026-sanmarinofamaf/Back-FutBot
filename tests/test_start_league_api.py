
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.database import get_db

from app.models.league import LeagueState
from app.services.league_service import (
    LeagueNotFound,
    LeagueForbidden,
    LeagueAlreadyStarted,
    InsufficientLeagueParticipants,
    InvalidLeagueState,
)

client = TestClient(app)


@pytest.fixture
def api_dependencies():
    user = SimpleNamespace(id=123)
    db = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    yield user, db

    app.dependency_overrides.clear()


@patch("app.api.leagues.start_league")
def test_start_league_success(mock_start, api_dependencies):
    user, db = api_dependencies

    response = client.patch(
        "/leagues/10",
        json={"state": "INICIADA"},
    )

    assert response.status_code == 204
    assert response.content == b""

    mock_start.assert_called_once_with(
        db=db,
        league_id=10,
        user_id=user.id,
        requested_state=LeagueState.INICIADA,
    )


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"state": "INVALIDA"},
        {"state": 123},
        [],
    ],
)
def test_invalid_body_returns_422(api_dependencies, body):
    response = client.patch(
        "/leagues/10",
        json=body,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "exception, expected_status",
    [
        (LeagueNotFound("League does not exist"), 404),
        (LeagueForbidden("Only creator can start"), 403),
        (LeagueAlreadyStarted("League already started"), 409),
        (InvalidLeagueState("Invalid transition"), 409),
        (InsufficientLeagueParticipants("Not enough clubs"), 409),
    ],
)
@patch("app.api.leagues.start_league")
def test_start_league_errors(
    mock_start,
    exception,
    expected_status,
    api_dependencies,
):
    mock_start.side_effect = exception

    response = client.patch(
        "/leagues/10",
        json={"state": "INICIADA"},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == str(exception)


def test_start_league_without_token_returns_401():
    app.dependency_overrides.clear()

    response = client.patch(
        "/leagues/10",
        json={"state": "INICIADA"},
    )

    assert response.status_code == 401
