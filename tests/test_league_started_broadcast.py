import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import leagues as leagues_api
from app.api.deps import get_current_user
from app.database import get_db
from app.models.match import MatchState
from app.schemas.league import (
    FixtureClub,
    FixtureMatchItem,
    StandingRow,
    LeagueStartedEvent,
)
from app.services.league_service import (
    LeagueNotFound,
    LeagueForbidden,
    LeagueAlreadyStarted,
    InvalidLeagueState,
    InsufficientLeagueParticipants,
)
from app.services.league_websocket_service import league_connection_manager

client = TestClient(app)


class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def send_json(self, value):
        self.sent.append(value)


def make_fixture() -> list[FixtureMatchItem]:
    return [
        FixtureMatchItem(
            match_id=1,
            match_order=1,
            round=1,
            state=MatchState.POR_COMENZAR,
            local=FixtureClub(club_id=1, name="Club 1"),
            visitante=FixtureClub(club_id=2, name="Club 2"),
        ),
        FixtureMatchItem(
            match_id=2,
            match_order=2,
            round=1,
            state=MatchState.POR_COMENZAR,
            local=FixtureClub(club_id=3, name="Club 3"),
            visitante=FixtureClub(club_id=1, name="Club 1"),
        ),
    ]


def make_standings() -> list[StandingRow]:
    return [
        StandingRow(
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
        for club_id in (1, 2, 3)
    ]


@pytest.fixture(autouse=True)
def clean_manager():
    league_connection_manager.active_connections.clear()
    yield
    league_connection_manager.active_connections.clear()


@pytest.fixture
def api_dependencies():
    user = SimpleNamespace(id=123)
    db = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    yield user, db

    app.dependency_overrides.clear()


@pytest.fixture
def connected_clients():
    # two clients in the league that starts and one in another league
    first, second, other_league = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()

    league_connection_manager.active_connections.update({
        10: {101: {first}, 102: {second}},
        20: {201: {other_league}},
    })

    return SimpleNamespace(
        first=first,
        second=second,
        other_league=other_league,
    )


@pytest.fixture
def start_dependencies():
    with (
        patch.object(leagues_api, "start_league") as start,
        patch.object(leagues_api.league_repository, "get_by_id", return_value=SimpleNamespace(id=10)),
        patch.object(leagues_api, "build_league_state", return_value=(make_fixture(), make_standings())),
        patch.object(leagues_api.session_websocket_service, "broadcast_leagues", new=AsyncMock()),
    ):
        yield start


# Verify that every client connected to the league receives league_started with fixture and standings
def test_connected_clients_receive_league_started(api_dependencies, connected_clients, start_dependencies):
    response = client.patch("/leagues/10", json={"state": "INICIADA"})

    assert response.status_code == 204

    for websocket in (connected_clients.first, connected_clients.second):
        assert len(websocket.sent) == 1

        event = websocket.sent[0]
        assert event["type"] == "league_started"
        assert event["league_id"] == 10
        assert [m["match_id"] for m in event["fixture"]] == [1, 2]
        assert event["fixture"][0]["local"]["club_id"] == 1
        assert event["fixture"][0]["visitante"]["club_id"] == 2
        assert len(event["standings"]) == 3
        assert all(row["points"] == 0 for row in event["standings"])


# Verify that a client connected to another league does not receive the event
def test_client_of_another_league_does_not_receive_league_started(
    api_dependencies, connected_clients, start_dependencies,
):
    response = client.patch("/leagues/10", json={"state": "INICIADA"})

    assert response.status_code == 204
    assert connected_clients.other_league.sent == []


# Verify that the event can be serialized to JSON, as a real websocket does
def test_league_started_payload_is_json_serializable(api_dependencies, connected_clients, start_dependencies):
    client.patch("/leagues/10", json={"state": "INICIADA"})

    payload = json.loads(json.dumps(connected_clients.first.sent[0]))

    assert payload["fixture"][0]["state"] == "POR_COMENZAR"


# Verify that the event is built after the league was started
def test_league_started_is_emitted_after_starting_the_league(api_dependencies, connected_clients, start_dependencies):
    def check_nothing_sent(**kwargs):
        assert connected_clients.first.sent == []

    start_dependencies.side_effect = check_nothing_sent

    client.patch("/leagues/10", json={"state": "INICIADA"})

    start_dependencies.assert_called_once()
    assert len(connected_clients.first.sent) == 1


# Verify that league_started is not emitted when the start is rejected
@pytest.mark.parametrize(
    "exception, expected_status",
    [
        (LeagueNotFound("League does not exist"), 404),
        (LeagueForbidden("Only the league creator can start the league"), 403),
        (LeagueAlreadyStarted("League cannot be started"), 409),
        (InvalidLeagueState("Invalid state transition"), 409),
        (InsufficientLeagueParticipants("League does not have enough participants"), 409),
    ],
)
def test_rejected_start_does_not_emit_league_started(
    api_dependencies, connected_clients, start_dependencies, exception, expected_status,
):
    start_dependencies.side_effect = exception

    response = client.patch("/leagues/10", json={"state": "INICIADA"})

    assert response.status_code == expected_status
    assert connected_clients.first.sent == []
    assert connected_clients.second.sent == []
    assert connected_clients.other_league.sent == []


# Verify that the manager sends league_started only to the given league
@pytest.mark.asyncio
async def test_manager_broadcasts_league_started_only_to_its_league(connected_clients):
    event = LeagueStartedEvent(
        league_id=10,
        fixture=make_fixture(),
        standings=make_standings(),
    )

    await league_connection_manager.broadcast(10, event)

    assert connected_clients.first.sent[0]["type"] == "league_started"
    assert connected_clients.second.sent[0]["type"] == "league_started"
    assert connected_clients.other_league.sent == []
