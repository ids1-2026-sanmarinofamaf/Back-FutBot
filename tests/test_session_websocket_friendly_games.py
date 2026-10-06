from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import asyncio
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_current_user_ws
from app.core.ws_manager import manager
from app.database import SessionLocal, get_db
from app.main import app
from app.models.club import Club
from app.models.friendly_game import FriendlyGame, FriendlyGameState
from app.models.user import User
from app.repositories import friendly_game_repository


client = TestClient(app)


class FakeWebSocket:
    # Websocket falso que guarda los JSON recibidos

    def __init__(self):
        self.accepted = False
        self.sent = []

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        self.sent.append(message)


def make_game(
    game_id: int,
    club_name: str,
    participants: int,
    state: FriendlyGameState,
):
    return SimpleNamespace(
        id=game_id,
        creator=SimpleNamespace(name=club_name),
        participations=[object() for _ in range(participants)],
        state=state,
    )


@pytest.fixture(autouse=True)
def clean_ws_state():
    manager.active.clear()
    app.dependency_overrides.clear()

    yield

    manager.active.clear()
    app.dependency_overrides.clear()


@pytest.fixture
def mocked_dependencies():
    user = SimpleNamespace(id=123)
    db = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_user_ws] = lambda: user

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    return user, db


def test_session_websocket_sends_initial_available_friendly_games(
    mocked_dependencies,
):
    _, db = mocked_dependencies

    available_game = make_game(
        game_id=10,
        club_name="San Marino",
        participants=1,
        state=FriendlyGameState.POR_COMENZAR,
    )

    with patch(
        "app.services.session_websocket_service."
        "friendly_game_repository.get_visible_friendly_games",
        return_value=[available_game],
    ) as mock_get_visible:

        with client.websocket_connect("/ws/sessions?token=test") as ws:
            payload = ws.receive_json()

    assert payload == {
        "friendly_games": [
            {
                "friendly_game_id": 10,
                "creator_club_name": "San Marino",
                "current_participants": 1,
                "capacity": 2,
                "state": "POR_COMENZAR",
            }
        ]
    }

    mock_get_visible.assert_called_once_with(db)


def test_visible_friendly_games_excludes_finished_games():
    db = SessionLocal()

    try:
        user = User(
            email="ws-visible@test.com",
            hash_passwd="hash",
        )
        club = Club(
            name="Visible Club",
            user=user,
        )

        db.add(user)
        db.flush()

        waiting = FriendlyGame(
            duration=100,
            creator_id=club.id,
            state=FriendlyGameState.POR_COMENZAR,
        )
        playing = FriendlyGame(
            duration=100,
            creator_id=club.id,
            state=FriendlyGameState.JUGANDO,
        )
        finished = FriendlyGame(
            duration=100,
            creator_id=club.id,
            state=FriendlyGameState.FINALIZADO,
        )

        db.add_all([waiting, playing, finished])
        db.commit()

        visible = friendly_game_repository.get_visible_friendly_games(db)

        visible_ids = {game.id for game in visible}

        assert waiting.id in visible_ids
        assert playing.id in visible_ids
        assert finished.id not in visible_ids

        assert {
            game.state
            for game in visible
        } <= {
            FriendlyGameState.POR_COMENZAR,
            FriendlyGameState.JUGANDO,
        }

    finally:
        db.rollback()
        db.query(FriendlyGame).filter(
            FriendlyGame.creator_id == club.id
        ).delete(synchronize_session=False)
        db.query(Club).filter(
            Club.id == club.id
        ).delete(synchronize_session=False)
        db.query(User).filter(
            User.id == user.id
        ).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_create_friendly_game_broadcasts_created_game_to_all_connections(
    mocked_dependencies,
):
    user, _ = mocked_dependencies

    connection_1 = FakeWebSocket()
    connection_2 = FakeWebSocket()

    asyncio.run(manager.connect(1, connection_1))
    asyncio.run(manager.connect(2, connection_2))

    created_game = make_game(
        game_id=25,
        club_name="Creator Club",
        participants=1,
        state=FriendlyGameState.POR_COMENZAR,
    )

    created_roster = SimpleNamespace(id=77)

    with (
        patch(
            "app.api.friendly_games.create_friendly_game",
            return_value=(created_game, created_roster),
        ) as mock_create,
        patch(
            "app.services.session_websocket_service."
            "friendly_game_repository.get_visible_friendly_games",
            return_value=[created_game],
        ),
    ):
        response = client.post(
            "/friendly_games",
            json={
                "duration": 100,
                "roster": {
                    "formation": "offensive",
                    "players": [],
                },
            },
        )

    assert response.status_code == 201
    assert response.json() == {
        "friendly_game_id": 25,
        "roster_id": 77,
    }

    mock_create.assert_called_once()
    assert mock_create.call_args.kwargs["user_id"] == user.id

    expected_payload = {
        "friendly_games": [
            {
                "friendly_game_id": 25,
                "creator_club_name": "Creator Club",
                "current_participants": 1,
                "capacity": 2,
                "state": "POR_COMENZAR",
            }
        ]
    }

    assert connection_1.sent == [expected_payload]
    assert connection_2.sent == [expected_payload]


def test_join_friendly_game_broadcasts_updated_capacity_to_all_connections(
    mocked_dependencies,
):
    _, _ = mocked_dependencies

    connection_1 = FakeWebSocket()
    connection_2 = FakeWebSocket()

    asyncio.run(manager.connect(1, connection_1))
    asyncio.run(manager.connect(2, connection_2))

    participation = SimpleNamespace(id=300)
    roster = SimpleNamespace(id=400)

    updated_game = make_game(
        game_id=30,
        club_name="Creator Club",
        participants=2,
        state=FriendlyGameState.POR_COMENZAR,
    )

    with (
        patch(
            "app.api.friendly_games.join_friendly_game",
            return_value=(participation, roster),
        ),
        patch(
            "app.services.session_websocket_service."
            "friendly_game_repository.get_visible_friendly_games",
            return_value=[updated_game],
        ),
    ):
        response = client.post(
            "/friendly_games/30/users",
            json={
                "roster": {
                    "formation": "defensive",
                    "players": [],
                },
            },
        )

    assert response.status_code == 201

    expected_payload = {
        "friendly_games": [
            {
                "friendly_game_id": 30,
                "creator_club_name": "Creator Club",
                "current_participants": 2,
                "capacity": 2,
                "state": "POR_COMENZAR",
            }
        ]
    }

    assert connection_1.sent == [expected_payload]
    assert connection_2.sent == [expected_payload]


def test_start_friendly_game_broadcasts_updated_state_to_all_connections(
    mocked_dependencies,
):
    _, _ = mocked_dependencies

    connection_1 = FakeWebSocket()
    connection_2 = FakeWebSocket()

    asyncio.run(manager.connect(1, connection_1))
    asyncio.run(manager.connect(2, connection_2))

    updated_game = make_game(
        game_id=40,
        club_name="Creator Club",
        participants=2,
        state=FriendlyGameState.JUGANDO,
    )

    with (
        patch(
            "app.api.friendly_games.start_friendly_game",
            new_callable=AsyncMock,
            return_value=900,
        ),
        patch(
            "app.services.session_websocket_service."
            "friendly_game_repository.get_visible_friendly_games",
            return_value=[updated_game],
        ),
    ):
        response = client.patch(
            "/friendly_games/40",
            json={
                "state": "JUGANDO",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "match_id": 900,
    }

    expected_payload = {
        "friendly_games": [
            {
                "friendly_game_id": 40,
                "creator_club_name": "Creator Club",
                "current_participants": 2,
                "capacity": 2,
                "state": "JUGANDO",
            }
        ]
    }

    assert connection_1.sent == [expected_payload]
    assert connection_2.sent == [expected_payload]
