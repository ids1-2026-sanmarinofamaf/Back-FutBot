
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.database import get_db

from app.services.league_service import (
    LeagueNotFound,
    LeagueCreatorCannotLeave,
    LeagueAlreadyStarted,
    LeagueParticipationNotFound,
)


client = TestClient(app)


@pytest.fixture
def api_dependencies():
    # mock authenticated user and database session
    user = SimpleNamespace(id=5)
    db = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    yield user, db

    app.dependency_overrides.clear()


# successful leave returns 204
@patch("app.api.leagues.leave_league")
def test_leave_league_success(mock_leave, api_dependencies):
    user, db = api_dependencies

    response = client.delete("/leagues/10/users/me")

    assert response.status_code == 204
    assert response.content == b""

    # verify service receives correct arguments
    mock_leave.assert_called_once_with(
        db=db,
        league_id=10,
        user_id=user.id,
    )


# nonexistent league returns 404
@patch("app.api.leagues.leave_league")
def test_leave_league_not_found(mock_leave, api_dependencies):
    mock_leave.side_effect = LeagueNotFound(
        "League does not exist"
    )

    response = client.delete("/leagues/999/users/me")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "League does not exist"
    }


# league creator cannot leave
@patch("app.api.leagues.leave_league")
def test_creator_cannot_leave(mock_leave, api_dependencies):
    mock_leave.side_effect = LeagueCreatorCannotLeave(
        "League creator cannot leave the league"
    )

    response = client.delete("/leagues/10/users/me")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "League creator cannot leave the league"
    }


# started league returns 409
@patch("app.api.leagues.leave_league")
def test_started_league_cannot_be_left(mock_leave, api_dependencies):
    mock_leave.side_effect = LeagueAlreadyStarted(
        "League has already started"
    )

    response = client.delete("/leagues/10/users/me")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "League has already started"
    }


# club not participating returns 404
@patch("app.api.leagues.leave_league")
def test_participation_not_found(mock_leave, api_dependencies):
    mock_leave.side_effect = LeagueParticipationNotFound(
        "User is not participating in this league"
    )

    response = client.delete("/leagues/10/users/me")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "User is not participating in this league"
    }


# missing authentication returns 401
@patch("app.api.leagues.leave_league")
def test_leave_league_without_token(mock_leave):
    app.dependency_overrides.clear()

    response = client.delete("/leagues/10/users/me")

    assert response.status_code == 401
    mock_leave.assert_not_called()


# invalid authentication returns 401
@patch("app.api.leagues.leave_league")
def test_leave_league_invalid_token(mock_leave):
    app.dependency_overrides.clear()

    response = client.delete(
        "/leagues/10/users/me",
        headers={
            "Authorization": "Bearer invalid.token.value"
        },
    )

    assert response.status_code == 401
    mock_leave.assert_not_called()


# invalid league id returns 422
@patch("app.api.leagues.leave_league")
def test_leave_league_invalid_id(mock_leave, api_dependencies):
    response = client.delete(
        "/leagues/invalid/users/me"
    )

    assert response.status_code == 422
    mock_leave.assert_not_called()
