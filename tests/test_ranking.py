from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.database import get_db
from app.schemas.ranking import RankingItem
from app.services.ranking_service import get_global_ranking
from app.repositories.ranking_repository import (
    get_global_ranking as get_ranking_repository,
)

client = TestClient(app)

@pytest.fixture
def api_dependencies():
    user = SimpleNamespace(id=5)
    db = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    yield db

    app.dependency_overrides.clear()


# successful ranking returns 200 with clubs and points
@patch("app.api.ranking.ranking_service.get_global_ranking")
def test_get_ranking_success(mock_ranking, api_dependencies):
    mock_ranking.return_value = [
        RankingItem(
            club_id=3,
            club_name="Barca",
            points=15,
        ),
        RankingItem(
            club_id=7,
            club_name="San Marino",
            points=9,
        ),
    ]

    response = client.get("/ranking")

    assert response.status_code == 200
    assert response.json() == [
        {
            "club_id": 3,
            "club_name": "Barca",
            "points": 15,
        },
        {
            "club_id": 7,
            "club_name": "San Marino",
            "points": 9,
        },
    ]

    mock_ranking.assert_called_once_with(api_dependencies)


# empty ranking returns 200 with empty list
@patch("app.api.ranking.ranking_service.get_global_ranking")
def test_get_ranking_empty(mock_ranking, api_dependencies):
    mock_ranking.return_value = []

    response = client.get("/ranking")

    assert response.status_code == 200
    assert response.json() == []


# missing or invalid token returns 401
@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer invalid.token.value"},
    ],
)
@patch("app.api.ranking.ranking_service.get_global_ranking")
def test_get_ranking_unauthorized(mock_ranking, headers):
    app.dependency_overrides.clear()

    response = client.get("/ranking", headers=headers)

    assert response.status_code == 401
    mock_ranking.assert_not_called()


# repository selects club information and orders by points
def test_get_ranking_ordered():
    db = MagicMock()
    db.execute.return_value.all.return_value = []

    get_ranking_repository(db)

    query = db.execute.call_args.args[0]
    sql = str(query)

    assert "clubs.id AS club_id" in sql
    assert "clubs.name AS club_name" in sql
    assert "club_statistics.total_points AS points" in sql
    assert "club_statistics.total_points DESC" in sql
    assert "clubs.id ASC" in sql


# ranking service returns club IDs, names and points
@patch("app.services.ranking_service.ranking_repository.get_global_ranking")
def test_ranking_service(mock_repository):
    db = MagicMock()

    mock_repository.return_value = [
        SimpleNamespace(
            club_id=3,
            club_name="Barca",
            points=15,
        ),
        SimpleNamespace(
            club_id=7,
            club_name="San Marino",
            points=9,
        ),
    ]

    result = get_global_ranking(db)

    assert [item.club_id for item in result] == [3, 7]
    assert [item.club_name for item in result] == ["Barca","San Marino"]
    assert [item.points for item in result] == [15, 9]

    mock_repository.assert_called_once_with(db)
