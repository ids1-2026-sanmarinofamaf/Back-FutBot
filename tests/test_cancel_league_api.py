from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import leagues as leagues_api
from app.api.deps import get_current_user
from app.database import get_db
from app.services.league_service import (
    LeagueNotFound,
    LeagueForbidden,
    LeagueAlreadyStarted,
)
from app.services.league_websocket_service import league_connection_manager


client = TestClient(app)


class FakeWebSocket:
    def __init__(self):
        self.sent = []
        self.closed = []

    async def accept(self):
        pass

    async def send_json(self, value):
        self.sent.append(value)

    async def close(self, code=1000, reason=""):
        self.closed.append((code, reason))


@pytest.fixture
def api_dependencies():
    user = SimpleNamespace(id=5)
    db = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    yield user, db

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clean_manager():
    league_connection_manager.active_connections.clear()
    league_connection_manager._send_locks.clear()
    league_connection_manager._ready_events.clear()
    yield
    league_connection_manager.active_connections.clear()
    league_connection_manager._send_locks.clear()
    league_connection_manager._ready_events.clear()


@patch("app.api.leagues.session_websocket_service.broadcast_leagues", new_callable=AsyncMock)
@patch("app.api.leagues.cancel_league")
def test_cancel_league_success(mock_cancel, mock_broadcast_leagues, api_dependencies):
    user, db = api_dependencies

    response = client.delete("/leagues/10")

    assert response.status_code == 204
    assert response.content == b""
    mock_cancel.assert_called_once_with(db=db, league_id=10, user_id=user.id)
    # the leagues listing is refreshed for connected users
    mock_broadcast_leagues.assert_awaited_once_with(db)


@pytest.mark.parametrize(
    "error,status_code",
    [
        (LeagueNotFound("League does not exist"), 404),
        (LeagueForbidden("Only the league creator can cancel the league"), 403),
        (LeagueAlreadyStarted("League cannot be cancelled"), 409),
    ],
)
@patch("app.api.leagues.session_websocket_service.broadcast_leagues", new_callable=AsyncMock)
@patch("app.api.leagues.league_connection_manager")
@patch("app.api.leagues.cancel_league")
def test_rejected_cancellation_returns_error_and_emits_nothing(
    mock_cancel,
    mock_manager,
    mock_broadcast_leagues,
    error,
    status_code,
    api_dependencies,
):
    mock_cancel.side_effect = error

    response = client.delete("/leagues/10")

    assert response.status_code == status_code
    assert response.json() == {"detail": str(error)}
    mock_manager.broadcast.assert_not_called()
    mock_manager.close_lobby.assert_not_called()
    mock_broadcast_leagues.assert_not_called()


@patch("app.api.leagues.cancel_league")
def test_cancel_league_without_token(mock_cancel):
    app.dependency_overrides.clear()

    response = client.delete("/leagues/10")

    assert response.status_code == 401
    mock_cancel.assert_not_called()


@pytest.mark.asyncio
@patch("app.api.leagues.session_websocket_service.broadcast_leagues", new_callable=AsyncMock)
@patch("app.api.leagues.cancel_league")
async def test_lobby_receives_league_cancelled_and_is_closed(mock_cancel, mock_broadcast_leagues):
    host_ws = FakeWebSocket()
    participant_ws = FakeWebSocket()
    other_league_ws = FakeWebSocket()

    await league_connection_manager.connect(10, 1, host_ws)
    await league_connection_manager.connect(10, 2, participant_ws)
    await league_connection_manager.connect(11, 3, other_league_ws)

    await leagues_api.cancel(
        league_id=10,
        db=MagicMock(),
        current_user=SimpleNamespace(id=1),
    )

    for websocket in (host_ws, participant_ws):
        assert websocket.sent == [{"type": "league_cancelled", "league_id": 10}]
        assert len(websocket.closed) == 1

    # the channel of the cancelled league is removed, other leagues are untouched
    assert 10 not in league_connection_manager.active_connections
    assert 11 in league_connection_manager.active_connections
    assert other_league_ws.sent == []
    assert other_league_ws.closed == []


@pytest.mark.asyncio
@patch("app.api.leagues.session_websocket_service.broadcast_leagues", new_callable=AsyncMock)
@patch("app.api.leagues.cancel_league")
async def test_rejected_cancellation_keeps_lobby_open(mock_cancel, mock_broadcast_leagues):
    mock_cancel.side_effect = LeagueForbidden("Only the league creator can cancel the league")
    websocket = FakeWebSocket()
    await league_connection_manager.connect(10, 2, websocket)

    with pytest.raises(Exception):
        await leagues_api.cancel(
            league_id=10,
            db=MagicMock(),
            current_user=SimpleNamespace(id=2),
        )

    assert websocket.sent == []
    assert websocket.closed == []
    assert 10 in league_connection_manager.active_connections
