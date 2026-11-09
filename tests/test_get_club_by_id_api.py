
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.database import get_db
from app.services.club_service import ClubNotFound

client = TestClient(app)


@pytest.fixture
def api_dependencies():
    db = MagicMock()
    user = SimpleNamespace(id=5)

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user

    yield db

    app.dependency_overrides.clear()


@patch("app.api.clubs.club_service.get_club_by_id")
def test_get_club_success(mock_service, api_dependencies):
    mock_service.return_value = {
        "club_name": "River",
        "club_avatar": "default",
        "statistics": {
            "total_points": 15,
            "matches_played": 6,
            "matches_won": 5,
            "matches_drawn": 0,
            "matches_lost": 1,
            "goals_for": 12,
            "goals_against": 4,
            "leagues_played": 2,
            "leagues_won": 1,
        },
    }

    response = client.get("/clubes/25")

    assert response.status_code == 200
    assert response.json() == mock_service.return_value

    
    mock_service.assert_called_once_with(api_dependencies, 25)

    # we dont return private info
    assert "email" not in response.json()
    assert "hash_passwd" not in response.json()


@patch("app.api.clubs.club_service.get_club_by_id")
def test_get_club_not_found(mock_service, api_dependencies):
    mock_service.side_effect = ClubNotFound()

    response = client.get("/clubes/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Club not found"


def test_get_club_without_token():
    app.dependency_overrides.clear()

    response = client.get("/clubes/25")

    assert response.status_code == 401


def test_get_club_invalid_token():
    app.dependency_overrides.clear()

    response = client.get(
        "/clubes/25",
        headers={"Authorization": "Bearer invalid.token"},
    )

    assert response.status_code == 401
