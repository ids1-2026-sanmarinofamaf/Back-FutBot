from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.database import get_db

from app.models.league import LeagueState, LeaguePrivacy
from app.models.match import MatchState
from app.schemas.league import (
    LeagueDetail,
    FixtureClub,
    FixtureMatchItem,
    StandingRow,
)
from app.services.league_service import LeagueNotFound

client = TestClient(app)


@pytest.fixture
def api_dependencies():
    user = SimpleNamespace(id=123)
    db = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    yield user, db

    app.dependency_overrides.clear()


def make_standing(club_id: int) -> StandingRow:
    return StandingRow(
        club_id=club_id,
        name=f"Club {club_id}",
        points=0,
        matches_played=0,
        matches_won=0,
        matches_drawn=0,
        matches_lost=0,
        goals_for=0,
        goals_against=0,
        goal_difference=0,
    )


@patch("app.api.leagues.get_league_detail")
def test_get_started_league_returns_fixture_and_standings(mock_detail, api_dependencies):
    _, db = api_dependencies

    mock_detail.return_value = LeagueDetail(
        league_id=10,
        name="Liga",
        state=LeagueState.INICIADA,
        privacy=LeaguePrivacy.PUBLICA,
        current_participants=2,
        capacity=8,
        fixture=[
            FixtureMatchItem(
                match_id=1,
                match_order=1,
                round=1,
                state=MatchState.POR_COMENZAR,
                local=FixtureClub(club_id=1, name="Club 1"),
                visitante=FixtureClub(club_id=2, name="Club 2"),
            )
        ],
        standings=[make_standing(1), make_standing(2)],
    )

    response = client.get("/leagues/10")

    assert response.status_code == 200

    body = response.json()
    assert body["state"] == "INICIADA"
    assert body["fixture"][0]["local"]["club_id"] == 1
    assert body["fixture"][0]["visitante"]["club_id"] == 2
    assert len(body["standings"]) == 2

    mock_detail.assert_called_once_with(db=db, league_id=10)


@patch("app.api.leagues.get_league_detail")
def test_get_league_not_started_has_no_fixture(mock_detail, api_dependencies):
    mock_detail.return_value = LeagueDetail(
        league_id=10,
        name="Liga",
        state=LeagueState.POR_COMENZAR,
        privacy=LeaguePrivacy.PUBLICA,
        current_participants=2,
        capacity=8,
    )

    response = client.get("/leagues/10")

    assert response.status_code == 200
    assert response.json()["fixture"] is None
    assert response.json()["standings"] is None


@patch("app.api.leagues.get_league_detail")
def test_get_league_not_found_returns_404(mock_detail, api_dependencies):
    mock_detail.side_effect = LeagueNotFound("League does not exist")

    response = client.get("/leagues/10")

    assert response.status_code == 404
    assert response.json()["detail"] == "League does not exist"


def test_get_league_without_token_returns_401():
    app.dependency_overrides.clear()

    response = client.get("/leagues/10")

    assert response.status_code == 401
