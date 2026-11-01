
import base64
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.database import get_db
from app.schemas.club import ClubUpdate
from app.services.club_service import update_club

client = TestClient(app)

PNG_AVATAR = base64.b64encode(
    b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
).decode()


@pytest.fixture
def api_dependencies():
    user = SimpleNamespace(
        id=5,
        email="test@mail.com",
        club=SimpleNamespace(name="Test Club"),
    )
    db = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    yield SimpleNamespace(user=user, db=db)

    app.dependency_overrides.clear()


# authenticated user can retrieve profile information
def test_get_user_profile_success(api_dependencies):
    response = client.get("/users/me")

    assert response.status_code == 200
    assert response.json() == {
        "user_name": "Test Club",
        "user_email": "test@mail.com",
        "user_id": "5",
    }


# authenticated user can retrieve club information and statistics
@patch("app.api.clubs.club_service.get_club")
def test_get_club_profile_success(mock_get_club, api_dependencies):
    mock_get_club.return_value = {
        "club_name": "Test Club",
        "club_avatar": "default",
        "statistics": {
            "total_points": 10,
            "matches_played": 5,
            "matches_won": 3,
            "matches_drawn": 1,
            "matches_lost": 1,
            "goals_for": 8,
            "goals_against": 4,
            "leagues_played": 2,
            "leagues_won": 1,
        },
    }

    response = client.get("/clubs/me")

    assert response.status_code == 200
    assert response.json() == mock_get_club.return_value

    mock_get_club.assert_called_once_with(
        api_dependencies.db,
        api_dependencies.user.id,
    )


# club name and avatar can be updated independently
@pytest.mark.parametrize(
    "body",
    [
        {"new_name": "New Club"},
        {"new_avatar": PNG_AVATAR},
    ],
)
@patch("app.api.clubs.club_service.update_club")
def test_update_club_success(mock_update, api_dependencies, body):
    response = client.put("/clubs/me", json=body)

    assert response.status_code == 204
    assert response.content == b""

    mock_update.assert_called_once()

    kwargs = mock_update.call_args.kwargs

    assert kwargs["db"] is api_dependencies.db
    assert kwargs["user_id"] == api_dependencies.user.id
    assert kwargs["data"] == ClubUpdate(**body)


# invalid tokens return 401 on all profile endpoints
@pytest.mark.parametrize(
    "method, endpoint",
    [
        ("GET", "/users/me"),
        ("GET", "/clubs/me"),
        ("PUT", "/clubs/me"),
    ],
)
def test_profile_invalid_token(method, endpoint):
    app.dependency_overrides.clear()

    response = client.request(
        method,
        endpoint,
        headers={"Authorization": "Bearer invalid.token.value"},
        json={"new_name": "New Club"} if method == "PUT" else None,
    )

    assert response.status_code == 401


# club updates are persisted in the database, we cant confirm that efectively persist in this test
@patch("app.services.club_service.club_repository.update_club")
@patch("app.services.club_service.club_repository.get_by_user_id")
def test_update_club_persistence(mock_get_club, mock_update):
    db = MagicMock()
    club = SimpleNamespace(name="Test Club", avatar="default")

    mock_get_club.return_value = club

    data = ClubUpdate(
        new_name="New Club",
        new_avatar=PNG_AVATAR,
    )

    update_club(db=db, user_id=5, data=data)

    mock_get_club.assert_called_once_with(db, 5)

    mock_update.assert_called_once_with(
        db=db,
        club=club,
        new_name="New Club",
        new_avatar=PNG_AVATAR,
    )

    db.commit.assert_called_once()
    db.rollback.assert_not_called()

# invalid request body returns 422
@pytest.mark.parametrize(
    "body",
    [
        {"new_name": "ab"},
        {"new_name": "Club 123"},
        {"new_avatar": "invalid_base64!"},
        {"new_avatar": base64.b64encode(b"GIF89a").decode()},
    ],
)
@patch("app.api.clubs.club_service.update_club")
def test_update_club_invalid_body(mock_update, api_dependencies, body):
    response = client.put("/clubs/me", json=body)

    assert response.status_code == 422
    mock_update.assert_not_called()