from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.database import get_db
from app.services.league_service import get_my_league_ids


client = TestClient(app)

USER_ID = 20
CLUB_ID = 30
URL = "/leagues/me"


@pytest.fixture
def api_dependencies():
    user = SimpleNamespace(id=USER_ID)
    db = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    yield user, db

    app.dependency_overrides.clear()


# endpoint tests
#returns 200 and ids
@patch("app.api.leagues.get_my_league_ids")
def test_get_my_leagues_success(mock_service, api_dependencies):
    user, db = api_dependencies

    mock_service.return_value = [1, 3, 5]

    response = client.get(URL)

    assert response.status_code == 200
    assert response.json() == {
        "league_ids": [1, 3, 5]
    }

    mock_service.assert_called_once_with(db, user.id)

# returnss 200 and empty list
@patch("app.api.leagues.get_my_league_ids")
def test_get_my_leagues_empty(mock_service, api_dependencies):
    mock_service.return_value = []

    response = client.get(URL)

    assert response.status_code == 200
    assert response.json() == {"league_ids": []}

# returns 401
def test_get_my_leagues_without_token():
    app.dependency_overrides.clear()

    response = client.get(URL)

    assert response.status_code == 401

# returns 401
def test_get_my_leagues_invalid_token():
    app.dependency_overrides.clear()

    response = client.get(
        URL,
        headers={
            "Authorization": "Bearer invalid.token.value"
        }
    )

    assert response.status_code == 401


# service tests
@patch(
    "app.services.league_service."
    "league_repository.get_active_league_ids_by_club"
)
@patch(
    "app.services.league_service."
    "club_repository.get_by_user_id"
)
def test_service_returns_league_ids(
    mock_get_club,
    mock_get_leagues,
):
    db = MagicMock()

    mock_get_club.return_value = SimpleNamespace(id=CLUB_ID)
    mock_get_leagues.return_value = [2, 4, 6]

    result = get_my_league_ids(db, USER_ID)

    assert result == [2, 4, 6]

    mock_get_club.assert_called_once_with(db, USER_ID)
    mock_get_leagues.assert_called_once_with(db, CLUB_ID)


@patch(
    "app.services.league_service."
    "league_repository.get_active_league_ids_by_club"
)
@patch(
    "app.services.league_service."
    "club_repository.get_by_user_id"
)
def test_service_without_club(
    mock_get_club,
    mock_get_leagues,
):
    db = MagicMock()

    mock_get_club.return_value = None

    result = get_my_league_ids(db, USER_ID)

    assert result == []
    mock_get_leagues.assert_not_called()


@patch(
    "app.services.league_service."
    "league_repository.get_active_league_ids_by_club"
)
@patch(
    "app.services.league_service."
    "club_repository.get_by_user_id"
)
def test_service_without_leagues(
    mock_get_club,
    mock_get_leagues,
):
    db = MagicMock()

    mock_get_club.return_value = SimpleNamespace(id=CLUB_ID)
    mock_get_leagues.return_value = []

    result = get_my_league_ids(db, USER_ID)

    assert result == []
    mock_get_leagues.assert_called_once_with(db, CLUB_ID)
