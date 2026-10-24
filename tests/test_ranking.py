from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.database import get_db
from app.schemas.ranking import RankingItem, RankingData
from app.services.ranking_service import get_global_ranking
from app.repositories.ranking_repository import get_global_ranking as get_ranking_repository


client = TestClient(app)


@pytest.fixture
def api_dependencies():
    user = SimpleNamespace(id=5)
    db = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    yield db

    app.dependency_overrides.clear()


# successful ranking returns 200 with user IDs and points
@patch("app.api.ranking.ranking_service.get_global_ranking")
def test_get_ranking_success(mock_ranking, api_dependencies):
    mock_ranking.return_value = [
        RankingItem(id_usuario=2, ranking_data=RankingData(points=15)),
        RankingItem(id_usuario=1, ranking_data=RankingData(points=9)),
    ]

    response = client.get("/ranking")

    assert response.status_code == 200
    assert response.json() == [
        {"id_usuario": 2, "ranking_data": {"points": 15}},
        {"id_usuario": 1, "ranking_data": {"points": 9}},
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


# ranking repository orders clubs by accumulated points
def test_get_ranking_ordered():
    db = MagicMock()
    db.execute.return_value.all.return_value = []

    get_ranking_repository(db)

    query = db.execute.call_args.args[0]
    sql = str(query)

    assert "club_statistics.total_points DESC" in sql


# ranking service returns user IDs and their ranking data
@patch("app.services.ranking_service.ranking_repository.get_global_ranking")
def test_ranking_service(mock_repository):
    db = MagicMock()

    mock_repository.return_value = [
        SimpleNamespace(id_usuario=2, points=15),
        SimpleNamespace(id_usuario=1, points=9),
    ]

    result = get_global_ranking(db)

    assert [item.id_usuario for item in result] == [2, 1]
    assert [item.ranking_data.points for item in result] == [15, 9]

    mock_repository.assert_called_once_with(db)