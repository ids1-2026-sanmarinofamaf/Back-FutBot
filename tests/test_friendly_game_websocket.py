import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import friendly_game_websocket as websocket_api

from app.models.friendly_game import FriendlyGameState
from app.models.friendly_game_participation import FriendlyGameRole

from app.schemas.friendly_game_websocket import (
    FriendlyGameLobbyState,
    FriendlyGameLobbyUser,
)

from app.services.friendly_game_websocket_service import (
    FriendlyGameConnectionManager,
    friendly_game_connection_manager,
)

import app.services.friendly_game_service as friendly_service


client = TestClient(app)

# ============================================================
# Helpers
# ============================================================

class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def accept(self):
        pass

    async def send_json(self, data):
        self.sent.append(data)

    async def close(self, code=1000, reason=""):
        pass


@pytest.fixture(autouse=True)
def clean_manager():
    friendly_game_connection_manager.active_connections.clear()
    yield
    friendly_game_connection_manager.active_connections.clear()


# ============================================================
# 1. Un participante puede conectarse al lobby
# ============================================================

def test_participant_can_connect_to_friendly_game(monkeypatch):
    user = SimpleNamespace(id=1)
    club = SimpleNamespace(id=10)

    friendly_game = SimpleNamespace(
        id=50,
        state=FriendlyGameState.POR_COMENZAR,
    )

    participation = SimpleNamespace(
        club_id=10,
    )

    initial_state = FriendlyGameLobbyState(
        friendly_game_id=50,
        state="POR_COMENZAR",
        current_users=1,
        match_id=None,
        users=[
            FriendlyGameLobbyUser(
                user_name="Club A",
                avatar="default",
                is_creator=True,  # ACTUALIZADO
            )
        ],
    )

    monkeypatch.setattr(
        websocket_api.auth_service,
        "get_user_from_token",
        MagicMock(return_value=user),
    )

    monkeypatch.setattr(
        websocket_api.club_repository,
        "get_by_user_id",
        MagicMock(return_value=club),
    )

    monkeypatch.setattr(
        websocket_api.friendly_game_repository,
        "get_by_id",
        MagicMock(return_value=friendly_game),
    )

    monkeypatch.setattr(
        websocket_api.friendly_game_repository,
        "get_participation_by_club",
        MagicMock(return_value=participation),
    )

    monkeypatch.setattr(
        websocket_api,
        "build_friendly_game_lobby_state",
        MagicMock(return_value=initial_state),
    )

    with client.websocket_connect(
        "/ws/friendly_game/50?token=valid"
    ) as websocket:

        message = websocket.receive_json()

        assert message["friendly_game_id"] == 50
        assert message["state"] == "POR_COMENZAR"
        assert message["users"][0]["is_creator"] is True  # NUEVO ASSERT

        assert 50 in friendly_game_connection_manager.active_connections

    assert 50 not in friendly_game_connection_manager.active_connections


# ============================================================
# 2. Dos amistosos están aislados + desconexión
# ============================================================

def test_lobbies_are_isolated_and_disconnected_user_receives_nothing():
    manager = FriendlyGameConnectionManager()

    ws_game_1 = FakeWebSocket()
    ws_game_2 = FakeWebSocket()

    asyncio.run(manager.connect(1, ws_game_1))
    asyncio.run(manager.connect(2, ws_game_2))

    state = FriendlyGameLobbyState(
        friendly_game_id=1,
        state="POR_COMENZAR",
        current_users=2,
        match_id=None,
        users=[],
    )

    asyncio.run(manager.broadcast(1, state))
    assert len(ws_game_1.sent) == 1
    assert ws_game_2.sent == []

    manager.disconnect(1, ws_game_1)
    asyncio.run(manager.broadcast(1, state))
    assert len(ws_game_1.sent) == 1


# ============================================================
# 3. JOIN exitoso manda actualización con el nuevo usuario
# ============================================================

@patch("app.services.friendly_game_service.friendly_game_connection_manager.broadcast", new_callable=AsyncMock)
@patch("app.services.friendly_game_service.build_friendly_game_lobby_state")
@patch("app.services.friendly_game_service.roster_repository")
@patch("app.services.friendly_game_service.behavior_repository")
@patch("app.services.friendly_game_service.player_repository")
@patch("app.services.friendly_game_service.club_repository")
@patch("app.services.friendly_game_service.friendly_game_repository")
def test_successful_join_broadcasts_new_participant(
    mock_friendly_repo,
    mock_club_repo,
    mock_player_repo,
    mock_behavior_repo,
    mock_roster_repo,
    mock_build_state,
    mock_broadcast,
):
    db = MagicMock()
    club = MagicMock()
    club.id = 2
    mock_club_repo.get_by_user_id.return_value = club

    game_before = MagicMock()
    game_before.id = 30
    game_before.state = FriendlyGameState.POR_COMENZAR
    game_after = MagicMock()
    game_after.id = 30
    game_after.state = FriendlyGameState.POR_COMENZAR

    mock_friendly_repo.get_by_id.side_effect = [game_before, game_after]
    mock_friendly_repo.get_participation_by_club.return_value = None
    mock_friendly_repo.count_participations.return_value = 1

    player = MagicMock()
    player.club_id = 2
    mock_player_repo.get_by_id.return_value = player

    behavior = MagicMock()
    behavior.is_default = True
    mock_behavior_repo.get_by_id.return_value = behavior

    def save_roster(db, roster):
        roster.id = 70
    mock_roster_repo.save.side_effect = save_roster

    mock_friendly_repo.create_participation.return_value = MagicMock(id=80)

    data = MagicMock()
    data.roster.formation = "offensive"
    players = []
    for player_id, slot in [(1, "left"), (2, "center"), (3, "right")]:
        p = MagicMock()
        p.player_id = player_id
        p.is_starter = True
        p.slot = slot
        p.initial_behavior_id = 1
        players.append(p)
    for player_id in [4, 5, 6]:
        p = MagicMock()
        p.player_id = player_id
        p.is_starter = False
        p.slot = None
        p.initial_behavior_id = None
        players.append(p)
    data.roster.players = players

    lobby_state = FriendlyGameLobbyState(
        friendly_game_id=30,
        state="POR_COMENZAR",
        current_users=2,
        match_id=None,
        users=[
            FriendlyGameLobbyUser(
                user_name="Club Host",
                avatar="host.png",
                is_creator=True,  # ACTUALIZADO
            ),
            FriendlyGameLobbyUser(
                user_name="Club Guest",
                avatar="guest.png",
                is_creator=False, # ACTUALIZADO
            ),
        ],
    )
    mock_build_state.return_value = lobby_state

    asyncio.run(
        friendly_service.join_friendly_game(
            db=db,
            friendly_game_id=30,
            user_id=5,
            data=data,
        )
    )

    db.commit.assert_called_once()
    mock_broadcast.assert_awaited_once_with(30, lobby_state)

    sent_state = mock_broadcast.await_args.args[1]
    assert sent_state.current_users == 2
    assert sent_state.users[1].user_name == "Club Guest"
    assert sent_state.users[1].avatar == "guest.png"
    assert sent_state.users[1].is_creator is False  # NUEVO ASSERT


# ============================================================
# 4. JOIN rechazado no manda actualización
# ============================================================

@patch("app.services.friendly_game_service.friendly_game_connection_manager.broadcast", new_callable=AsyncMock)
@patch("app.services.friendly_game_service.club_repository")
@patch("app.services.friendly_game_service.friendly_game_repository")
def test_rejected_join_does_not_broadcast(
    mock_friendly_repo,
    mock_club_repo,
    mock_broadcast,
):
    db = MagicMock()
    club = MagicMock()
    club.id = 2
    mock_club_repo.get_by_user_id.return_value = club

    friendly_game = MagicMock()
    friendly_game.id = 30
    friendly_game.state = FriendlyGameState.POR_COMENZAR
    mock_friendly_repo.get_by_id.return_value = friendly_game
    mock_friendly_repo.get_participation_by_club.return_value = None
    mock_friendly_repo.count_participations.return_value = 2

    with pytest.raises(friendly_service.FriendlyGameFull):
        asyncio.run(
            friendly_service.join_friendly_game(
                db=db,
                friendly_game_id=30,
                user_id=5,
                data=MagicMock(),
            )
        )
    mock_broadcast.assert_not_awaited()


# ============================================================
# 5. START exitoso manda JUGANDO + match_id
# ============================================================

@patch("app.services.friendly_game_service.friendly_game_connection_manager.close_lobby", new_callable=AsyncMock)
@patch("app.services.friendly_game_service.friendly_game_connection_manager.broadcast", new_callable=AsyncMock)
@patch("app.services.friendly_game_service.build_friendly_game_lobby_state")
@patch("app.services.friendly_game_service.start_match")
@patch("app.services.friendly_game_service.load_match_behaviors")
@patch("app.services.friendly_game_service._create_match_participation")
@patch("app.services.friendly_game_service.club_repository")
@patch("app.services.friendly_game_service.friendly_game_repository")
def test_successful_start_broadcasts_match_id(
    mock_friendly_repo,
    mock_club_repo,
    mock_create_participation,
    mock_load_behaviors,
    mock_start_match,
    mock_build_state,
    mock_broadcast,
    mock_close_lobby,
):
    db = MagicMock()
    creator = MagicMock()
    creator.role = FriendlyGameRole.CREATOR
    guest = MagicMock()
    guest.role = FriendlyGameRole.GUEST

    friendly_game = MagicMock()
    friendly_game.id = 10
    friendly_game.creator_id = 1
    friendly_game.duration = 100
    friendly_game.state = FriendlyGameState.POR_COMENZAR
    friendly_game.participations = [creator, guest]
    mock_friendly_repo.get_by_id.return_value = friendly_game

    club = MagicMock()
    club.id = 1
    mock_club_repo.get_by_user_id.return_value = club

    mock_create_participation.side_effect = [MagicMock(), MagicMock()]
    mock_load_behaviors.return_value = []
    mock_start_match.return_value = 55

    def update_state(db, friendly_game, state):
        friendly_game.state = state
    mock_friendly_repo.update_state.side_effect = update_state

    lobby_state = FriendlyGameLobbyState(
        friendly_game_id=10,
        state="JUGANDO",
        current_users=2,
        match_id=55,
        users=[],
    )
    mock_build_state.return_value = lobby_state

    result = asyncio.run(
        friendly_service.start_friendly_game(
            db=db,
            friendly_game_id=10,
            user_id=5,
            requested_state=FriendlyGameState.JUGANDO,
        )
    )

    assert result == 55
    mock_broadcast.assert_awaited_once_with(10, lobby_state)
    sent_state = mock_broadcast.await_args.args[1]
    assert sent_state.state == "JUGANDO"
    assert sent_state.match_id == 55
    mock_close_lobby.assert_awaited_once()


# ============================================================
# 6. START rechazado no manda actualización
# ============================================================

@patch("app.services.friendly_game_service.friendly_game_connection_manager.broadcast", new_callable=AsyncMock)
@patch("app.services.friendly_game_service.club_repository")
@patch("app.services.friendly_game_service.friendly_game_repository")
def test_rejected_start_does_not_broadcast(
    mock_friendly_repo,
    mock_club_repo,
    mock_broadcast,
):
    db = MagicMock()
    friendly_game = MagicMock()
    friendly_game.id = 10
    friendly_game.creator_id = 1
    friendly_game.state = FriendlyGameState.POR_COMENZAR
    mock_friendly_repo.get_by_id.return_value = friendly_game

    club = MagicMock()
    club.id = 99
    mock_club_repo.get_by_user_id.return_value = club

    with pytest.raises(friendly_service.FriendlyGameForbiddenError):
        asyncio.run(
            friendly_service.start_friendly_game(
                db=db,
                friendly_game_id=10,
                user_id=5,
                requested_state=FriendlyGameState.JUGANDO,
            )
        )
    mock_broadcast.assert_not_awaited()