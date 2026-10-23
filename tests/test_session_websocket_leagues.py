from types import SimpleNamespace
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from app.schemas.friendly_game import FriendlyGamesSessionPayload
from app.models.league import LeaguePrivacy, LeagueState
from app.schemas.league import LeaguesSessionPayload, LeagueSessionItem
from app.services.session_websocket_service import (
    build_leagues_payload,
    broadcast_leagues,
    send_session_snapshot_to_connection,
)

def make_league(
    league_id: int,
    name: str = "Test League",
    participants: int = 2,
    capacity: int = 8,
    privacy: LeaguePrivacy = LeaguePrivacy.PUBLICA,
    state: LeagueState = LeagueState.POR_COMENZAR,
):
    return SimpleNamespace(
        id=league_id,
        name=name,
        league_participations=[
            SimpleNamespace()
            for _ in range(participants)
        ],
        max_clubs=capacity,
        privacy=privacy,
        state=state,
        password_hash="secret_hash",
        creator_id=99,
    )


@patch(
    "app.services.session_websocket_service."
    "league_repository.get_visible_leagues"
)
def test_build_leagues_payload_returns_empty_list(mock_get_visible):
    mock_get_visible.return_value = []

    db = object()

    payload = build_leagues_payload(db)

    assert payload.model_dump(mode="json") == {
        "leagues": [],
    }

    mock_get_visible.assert_called_once_with(db)


@patch(
    "app.services.session_websocket_service."
    "league_repository.get_visible_leagues"
)
def test_build_leagues_payload_maps_league_fields(mock_get_visible):
    mock_get_visible.return_value = [
        make_league(
            league_id=1,
            name="Liga Argentina",
            participants=4,
            capacity=8,
        )
    ]

    payload = build_leagues_payload(object())

    assert payload.model_dump(mode="json") == {
        "leagues": [
            {
                "league_id": 1,
                "name": "Liga Argentina",
                "current_participants": 4,
                "capacity": 8,
                "privacy": "PUBLICA",
                "state": "POR_COMENZAR",
            }
        ]
    }


@patch(
    "app.services.session_websocket_service."
    "league_repository.get_visible_leagues"
)
def test_build_leagues_payload_handles_private_started_league(
    mock_get_visible,
):
    mock_get_visible.return_value = [
        make_league(
            league_id=2,
            name="Liga Privada",
            participants=6,
            capacity=6,
            privacy=LeaguePrivacy.PRIVADA,
            state=LeagueState.INICIADA,
        )
    ]

    payload = build_leagues_payload(object())

    assert payload.model_dump(mode="json") == {
        "leagues": [
            {
                "league_id": 2,
                "name": "Liga Privada",
                "current_participants": 6,
                "capacity": 6,
                "privacy": "PRIVADA",
                "state": "INICIADA",
            }
        ]
    }


@patch(
    "app.services.session_websocket_service."
    "league_repository.get_visible_leagues"
)
def test_build_leagues_payload_does_not_expose_sensitive_fields(
    mock_get_visible,
):
    mock_get_visible.return_value = [
        make_league(league_id=3)
    ]

    payload = build_leagues_payload(object())

    serialized = payload.model_dump(mode="json")
    league_data = serialized["leagues"][0]

    assert "password_hash" not in league_data
    assert "creator_id" not in league_data
    assert "league_participations" not in league_data


@pytest.mark.asyncio
@patch(
    "app.services.session_websocket_service.manager.broadcast",
    new_callable=AsyncMock,
)
@patch(
    "app.services.session_websocket_service.build_leagues_payload"
)
async def test_broadcast_leagues_sends_payload(
    mock_build_payload,
    mock_broadcast,
):
    db = object()

    mock_build_payload.return_value = LeaguesSessionPayload(
        leagues=[
            LeagueSessionItem(
                league_id=1,
                name="Liga Argentina",
                current_participants=4,
                capacity=8,
                privacy=LeaguePrivacy.PUBLICA,
                state=LeagueState.POR_COMENZAR,
            )
        ]
    )

    await broadcast_leagues(db)

    mock_build_payload.assert_called_once_with(db)
    mock_broadcast.assert_awaited_once_with(
        {
            "leagues": [
                {
                    "league_id": 1,
                    "name": "Liga Argentina",
                    "current_participants": 4,
                    "capacity": 8,
                    "privacy": "PUBLICA",
                    "state": "POR_COMENZAR",
                }
            ]
        }
    )


@pytest.mark.asyncio
@patch(
    "app.services.session_websocket_service.build_leagues_payload"
)
@patch(
    "app.services.session_websocket_service.build_friendly_games_payload"
)
async def test_send_session_snapshot_includes_both_categories(
    mock_build_friendly,
    mock_build_leagues,
):
    db = object()
    websocket = MagicMock()
    websocket.send_json = AsyncMock()

    mock_build_friendly.return_value = FriendlyGamesSessionPayload(
        friendly_games=[]
    )
    mock_build_leagues.return_value = LeaguesSessionPayload(
        leagues=[
            LeagueSessionItem(
                league_id=1,
                name="Liga Argentina",
                current_participants=4,
                capacity=8,
                privacy=LeaguePrivacy.PUBLICA,
                state=LeagueState.POR_COMENZAR,
            )
        ]
    )

    await send_session_snapshot_to_connection(
        websocket=websocket,
        db=db,
    )

    mock_build_friendly.assert_called_once_with(db)
    mock_build_leagues.assert_called_once_with(db)

    websocket.send_json.assert_awaited_once_with(
        {
            "friendly_games": [],
            "leagues": [
                {
                    "league_id": 1,
                    "name": "Liga Argentina",
                    "current_participants": 4,
                    "capacity": 8,
                    "privacy": "PUBLICA",
                    "state": "POR_COMENZAR",
                }
            ],
        }
    )
