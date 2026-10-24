
import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.api import league_websocket as ws_api
from app.services import league_service
from app.models.league import LeagueState, LeaguePrivacy
from app.schemas.league_websocket import LeagueUserEvent
from app.services.league_websocket_service import (
    LeagueConnectionManager,
    build_league_user_event,
    build_league_lobby_state,
    league_connection_manager,
)


class FakeWebSocket:
    def __init__(self):
        self.sent = []
        self.closed = []
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, value):
        self.sent.append(value)

    async def close(self, code=1000, reason=""):
        self.closed.append((code, reason))


def club(club_id, name=None):
    return SimpleNamespace(id=club_id, name=name or f"Club {club_id}", avatar="default")


def league(league_id=10, members=(1, 2)):
    participants = [SimpleNamespace(club_id=i, club=club(i)) for i in members]
    return SimpleNamespace(
        id=league_id,
        creator_id=members[0],
        state=LeagueState.POR_COMENZAR,
        privacy=LeaguePrivacy.PUBLICA,
        max_clubs=8,
        league_participations=participants,
    )


@pytest.fixture(autouse=True)
def clean_manager():
    league_connection_manager.active_connections.clear()
    yield
    league_connection_manager.active_connections.clear()


@pytest.fixture
def websocket_dependencies():
    @contextmanager
    def fake_session():
        yield MagicMock()

    user = SimpleNamespace(id=101)
    active_league = league(10)
    active_club = club(1)
    with (
        patch.object(ws_api, "SessionLocal", fake_session),
        patch.object(ws_api.auth_service, "get_user_from_token", return_value=user),
        patch.object(ws_api.league_repository, "get_by_id", return_value=active_league),
        patch.object(ws_api.club_repository, "get_by_user_id", return_value=active_club),
        patch.object(
            ws_api.league_participation_repository,
            "get_participation_by_club_and_league",
            return_value=SimpleNamespace(club_id=1, league_id=10),
        ) as participation_lookup,
    ):
        yield SimpleNamespace(
            user=user, league=active_league, club=active_club,
            participation_lookup=participation_lookup,
        )


# Verify that a league participant can connect and receive the initial lobby state
def test_participant_connects_and_receives_initial_state(websocket_dependencies):
    with TestClient(app) as client:
        with client.websocket_connect("/ws/leagues/10?token=valid") as ws:
            message = ws.receive_json()
            assert message == {
                "type": "lobby_state", "league_id": 10,
                "state": "POR_COMENZAR", "current_users": 2,
                "users": [
                    {"club_id": 1, "user_name": "Club 1", "avatar": "default", "is_creator": True},
                    {"club_id": 2, "user_name": "Club 2", "avatar": "default", "is_creator": False},
                ],
            }
            assert 101 in league_connection_manager.active_connections[10]
    assert not league_connection_manager.active_connections


# Verify that connections without a token or league participation are rejected
@pytest.mark.parametrize("url,expected", [
    ("/ws/leagues/10", 4401),
    ("/ws/leagues/10?token=valid", 4403),
])
def test_connection_rejected_without_token_or_participation(
    websocket_dependencies, url, expected
):
    if expected == 4403:
        websocket_dependencies.participation_lookup.return_value = None
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect(url) as ws:
                ws.receive_json()
    assert error.value.code == expected
    assert not league_connection_manager.active_connections

# Verify that connecting to a nonexistent league is rejected with code 4404
def test_league_not_found_returns_4404(websocket_dependencies):
    with patch.object(
        ws_api.league_repository,
        "get_by_id",
        return_value=None,
    ):
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as error:
                with client.websocket_connect("/ws/leagues/999?token=valid") as ws:
                    ws.receive_json()

    assert error.value.code == 4404
    assert not league_connection_manager.active_connections


# Verify that all connected users receive join events without affecting other leagues
@pytest.mark.asyncio
async def test_two_leagues_are_isolated_and_every_connected_client_receives_join():
    manager = LeagueConnectionManager()
    a, b, other = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()
    await manager.connect(10, 101, a)
    await manager.connect(10, 102, b)
    await manager.connect(20, 201, other)
    event = build_league_user_event(league(), club(3), "user_joined")
    await manager.broadcast(10, event)
    for websocket in (a, b):
        assert len(websocket.sent) == 1
        assert websocket.sent[0]["type"] == "user_joined"
        assert websocket.sent[0]["user"] == {
            "club_id": 3, "user_name": "Club 3", "avatar": "default", "is_creator": False,
        }
    assert other.sent == []


# Verify that all connected users receive a leave event identifying the departing club
@pytest.mark.asyncio
async def test_every_connected_client_receives_left_and_can_remove_club():
    manager = LeagueConnectionManager()
    a, b = FakeWebSocket(), FakeWebSocket()
    await manager.connect(10, 101, a)
    await manager.connect(10, 102, b)
    event = build_league_user_event(league(), club(2), "user_left")
    await manager.broadcast(10, event)
    assert all(ws.sent[0]["type"] == "user_left" for ws in (a, b))
    assert all(ws.sent[0]["user"]["club_id"] == 2 for ws in (a, b))
    assert all(ws.sent[0]["league_id"] == 10 for ws in (a, b))


# Verify that a disconnected client stops receiving events while others remain connected
@pytest.mark.asyncio
async def test_closed_connection_receives_no_further_events():
    manager = LeagueConnectionManager()
    a, b = FakeWebSocket(), FakeWebSocket()
    await manager.connect(10, 101, a)
    await manager.connect(10, 102, b)
    manager.disconnect(10, 101, a)
    event = build_league_user_event(league(), club(3), "user_joined")
    await manager.broadcast(10, event)
    assert a.sent == []
    assert len(b.sent) == 1
    assert 101 not in manager.active_connections[10]


# Verify that leaving a league closes all of the user's connections with code 1008
@pytest.mark.asyncio
async def test_formal_leave_closes_all_user_connections():
    manager = LeagueConnectionManager()
    a, duplicate, b = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()
    await manager.connect(10, 101, a)
    await manager.connect(10, 101, duplicate)
    await manager.connect(10, 102, b)
    await manager.disconnect_user(10, 101)
    assert a.closed == [(1008, "User left the league")]
    assert duplicate.closed == [(1008, "User left the league")]
    assert b.closed == []
    event = build_league_user_event(league(), club(3), "user_joined")
    await manager.broadcast(10, event)
    assert a.sent == duplicate.sent == []
    assert len(b.sent) == 1


@pytest.fixture
def service_repos():
    l = league()
    c = club(2)
    participant = SimpleNamespace(roster=SimpleNamespace(id=30), club_id=2, league_id=10)
    with (
        patch.object(league_service, "league_repository") as league_repo,
        patch.object(league_service, "club_repository") as club_repo,
        patch.object(league_service, "league_participation_repository") as participation_repo,
        patch.object(league_service, "roster_repository") as roster_repo,
        patch.object(league_service, "league_connection_manager") as manager,
    ):
        league_repo.get_by_id.return_value = l
        league_repo.count_participations.return_value = 2
        club_repo.get_by_user_id.return_value = c
        participation_repo.get_participation_by_club_and_league.return_value = participant
        manager.broadcast = AsyncMock()
        manager.disconnect_user = AsyncMock()
        yield SimpleNamespace(
            league=l, club=c, participant=participant,
            league_repo=league_repo, participation_repo=participation_repo,
            roster_repo=roster_repo, manager=manager,
        )


# Verify that a successful leave broadcasts user_left after the database commit
@pytest.mark.asyncio
async def test_successful_leave_broadcasts_after_commit(service_repos):
    db = MagicMock()
    await league_service.leave_league(db, 10, 101)
    db.commit.assert_called_once()
    service_repos.manager.broadcast.assert_awaited_once()
    kwargs = service_repos.manager.broadcast.await_args.kwargs
    assert kwargs["league_id"] == 10
    assert kwargs["state"].type == "user_left"
    assert kwargs["state"].user.club_id == 2
    service_repos.manager.disconnect_user.assert_awaited_once_with(league_id=10, user_id=101)


# Verify that rejected or failed leave operations do not broadcast events
@pytest.mark.parametrize("failure", ["rejected", "commit_failed"])
@pytest.mark.asyncio
async def test_rejected_or_unpersisted_leave_does_not_broadcast(service_repos, failure):
    db = MagicMock()
    if failure == "rejected":
        service_repos.participation_repo.get_participation_by_club_and_league.return_value = None
        expected = league_service.LeagueParticipationNotFound
    else:
        db.commit.side_effect = RuntimeError("commit failed")
        expected = RuntimeError
    with pytest.raises(expected):
        await league_service.leave_league(db, 10, 101)
    service_repos.manager.broadcast.assert_not_awaited()
    service_repos.manager.disconnect_user.assert_not_awaited()


# Verify that joining an already joined league does not emit user_joined
@pytest.mark.asyncio
async def test_rejected_join_does_not_broadcast(service_repos):
    db = MagicMock()
    service_repos.participation_repo.get_participation_by_club_and_league.return_value = service_repos.participant
    with pytest.raises(league_service.AlreadyParticipating):
        await league_service.join_league(db, 10, 101, MagicMock())
    service_repos.manager.broadcast.assert_not_awaited()


# Verify that a failed database commit prevents the user_joined broadcast
@pytest.mark.asyncio
async def test_unpersisted_join_does_not_broadcast(service_repos):
    db = MagicMock()
    service_repos.participation_repo.get_participation_by_club_and_league.return_value = None
    data = MagicMock()
    data.roster.players = []
    with patch.object(league_service.Roster, "validate_roster", return_value=None):
        service_repos.participation_repo.create_participation.return_value = SimpleNamespace(
            league_id=10, club_id=2, roster_id=30
        )
        db.commit.side_effect = RuntimeError("commit failed")
        with pytest.raises(RuntimeError, match="commit failed"):
            await league_service.join_league(db, 10, 101, data)
    service_repos.manager.broadcast.assert_not_awaited()


# Verify that a successful join broadcasts user_joined with the new club's data
@pytest.mark.asyncio
async def test_successful_join_broadcasts_after_commit(service_repos):
    db = MagicMock()
    service_repos.participation_repo.get_participation_by_club_and_league.return_value = None
    data = MagicMock()
    data.roster.players = []
    with patch.object(league_service.Roster, "validate_roster", return_value=None):
        service_repos.participation_repo.create_participation.return_value = SimpleNamespace(
            league_id=10, club_id=2, roster_id=30
        )
        await league_service.join_league(db, 10, 101, data)
    db.commit.assert_called_once()
    service_repos.manager.broadcast.assert_awaited_once()
    kwargs = service_repos.manager.broadcast.await_args.kwargs
    assert kwargs["league_id"] == 10
    assert isinstance(kwargs["state"], LeagueUserEvent)
    assert kwargs["state"].type == "user_joined"
    assert kwargs["state"].user.club_id == 2


# Verify that the initial lobby state includes all participants and identifies the creator
def test_build_league_lobby_state():
    club1 = SimpleNamespace(
        id=1,
        name="Club A",
        avatar="default",
    )

    club2 = SimpleNamespace(
        id=2,
        name="Club B",
        avatar="default",
    )

    league = SimpleNamespace(
        id=10,
        creator_id=1,
        state=LeagueState.POR_COMENZAR,
        league_participations=[
            SimpleNamespace(club_id=1, club=club1),
            SimpleNamespace(club_id=2, club=club2),
        ],
    )

    state = build_league_lobby_state(league)

    assert state.type == "lobby_state"
    assert state.league_id == 10
    assert state.state == "POR_COMENZAR"
    assert state.current_users == 2

    assert len(state.users) == 2

    assert state.users[0].club_id == 1
    assert state.users[0].user_name == "Club A"
    assert state.users[0].is_creator is True

    assert state.users[1].club_id == 2
    assert state.users[1].user_name == "Club B"
    assert state.users[1].is_creator is False

