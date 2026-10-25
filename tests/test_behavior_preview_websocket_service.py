from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from app.services.behavior_preview_websocket_service import (
    PreviewConnectionManager,
)
from app.services.match_websocket_service import build_match_state_message

from app.schemas.behavior_preview import BehaviorPreviewFinishedMessage

from app.game.preview_match import create_preview_match


@pytest.fixture
def manager():
    return PreviewConnectionManager()


@pytest.fixture
def preview_id():
    return uuid4()


@pytest.fixture
def websocket():
    websocket = AsyncMock()
    return websocket


@pytest.mark.asyncio
async def test_connect_registers_websocket(
    manager,
    preview_id,
    websocket,
):
    await manager.connect(preview_id, websocket)

    websocket.accept.assert_awaited_once()
    assert manager.active_connections[preview_id] == [websocket]


@pytest.mark.asyncio
async def test_connect_allows_multiple_websockets(
    manager,
    preview_id,
):
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await manager.connect(preview_id, ws1)
    await manager.connect(preview_id, ws2)

    assert manager.active_connections[preview_id] == [ws1, ws2]


@pytest.mark.asyncio
async def test_disconnect_removes_only_requested_websocket(
    manager,
    preview_id,
):
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await manager.connect(preview_id, ws1)
    await manager.connect(preview_id, ws2)

    manager.disconnect(preview_id, ws1)

    assert manager.active_connections[preview_id] == [ws2]


@pytest.mark.asyncio
async def test_disconnect_removes_preview_when_empty(
    manager,
    preview_id,
    websocket,
):
    await manager.connect(preview_id, websocket)

    manager.disconnect(preview_id, websocket)

    assert preview_id not in manager.active_connections


def test_disconnect_unknown_preview_does_nothing(
    manager,
    preview_id,
    websocket,
):
    manager.disconnect(preview_id, websocket)

    assert manager.active_connections == {}


@pytest.mark.asyncio
async def test_connect_registers_websocket(
    manager,
    preview_id,
    websocket,
):
    await manager.connect(preview_id, websocket)

    websocket.accept.assert_awaited_once()
    assert manager.active_connections[preview_id] == [websocket]


@pytest.mark.asyncio
async def test_connect_allows_multiple_websockets(
    manager,
    preview_id,
):
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await manager.connect(preview_id, ws1)
    await manager.connect(preview_id, ws2)

    assert manager.active_connections[preview_id] == [ws1, ws2]


@pytest.mark.asyncio
async def test_disconnect_removes_only_requested_websocket(
    manager,
    preview_id,
):
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await manager.connect(preview_id, ws1)
    await manager.connect(preview_id, ws2)

    manager.disconnect(preview_id, ws1)

    assert manager.active_connections[preview_id] == [ws2]


@pytest.mark.asyncio
async def test_disconnect_removes_preview_when_empty(
    manager,
    preview_id,
    websocket,
):
    await manager.connect(preview_id, websocket)

    manager.disconnect(preview_id, websocket)

    assert preview_id not in manager.active_connections


def test_disconnect_unknown_preview_does_nothing(
    manager,
    preview_id,
    websocket,
):
    manager.disconnect(preview_id, websocket)

    assert manager.active_connections == {}


@pytest.mark.asyncio
async def test_broadcast_sends_message_to_all_connections(
    manager,
    preview_id,
):
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await manager.connect(preview_id, ws1)
    await manager.connect(preview_id, ws2)

    message = BehaviorPreviewFinishedMessage(reason="completed")

    await manager.broadcast(preview_id, message)

    expected = {
        "event": "preview_finished",
        "reason": "completed",
    }

    ws1.send_json.assert_awaited_once_with(expected)
    ws2.send_json.assert_awaited_once_with(expected)


@pytest.mark.asyncio
async def test_broadcast_does_not_send_to_other_previews(
    manager,
):
    preview_1 = uuid4()
    preview_2 = uuid4()

    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await manager.connect(preview_1, ws1)
    await manager.connect(preview_2, ws2)

    message = BehaviorPreviewFinishedMessage(reason="completed")

    await manager.broadcast(preview_1, message)

    ws1.send_json.assert_awaited_once()
    ws2.send_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_broadcast_removes_failed_connections(
    manager,
    preview_id,
):
    failed_ws = AsyncMock()
    healthy_ws = AsyncMock()

    failed_ws.send_json.side_effect = RuntimeError(
        "Connection lost"
    )

    await manager.connect(preview_id, failed_ws)
    await manager.connect(preview_id, healthy_ws)

    message = BehaviorPreviewFinishedMessage(reason="stopped")

    await manager.broadcast(preview_id, message)

    assert manager.active_connections[preview_id] == [healthy_ws]

    healthy_ws.send_json.assert_awaited_once_with(
        message.model_dump()
    )


@pytest.mark.asyncio
async def test_close_preview_closes_all_connections(
    manager,
    preview_id,
):
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await manager.connect(preview_id, ws1)
    await manager.connect(preview_id, ws2)

    await manager.close_preview_connection(preview_id)

    ws1.close.assert_awaited_once()
    ws2.close.assert_awaited_once()

    assert preview_id not in manager.active_connections


@pytest.mark.asyncio
async def test_close_preview_continues_if_connection_fails(
    manager,
    preview_id,
):
    failed_ws = AsyncMock()
    healthy_ws = AsyncMock()

    failed_ws.close.side_effect = RuntimeError(
        "Connection already closed"
    )

    await manager.connect(preview_id, failed_ws)
    await manager.connect(preview_id, healthy_ws)

    await manager.close_preview_connection(preview_id)

    healthy_ws.close.assert_awaited_once()
    assert preview_id not in manager.active_connections


@pytest.mark.asyncio
async def test_broadcast_removes_preview_when_all_connections_fail(
    manager,
    preview_id,
    websocket,
):
    websocket.send_json.side_effect = RuntimeError(
        "Connection lost"
    )

    await manager.connect(preview_id, websocket)

    message = BehaviorPreviewFinishedMessage(reason="completed")

    await manager.broadcast(preview_id, message)

    assert preview_id not in manager.active_connections


@pytest.mark.asyncio
async def test_broadcast_match_snapshot(
    manager,
    preview_id,
    websocket,
):
    preview = create_preview_match(
        behavior_teammate_1=10,
        behavior_teammate_2=20,
        default_behaviors_ids={
            "Attacker": 101,
            "Midfielder": 102,
            "Defender": 103,
        },
    )

    snapshot = preview.snapshot()
    message = build_match_state_message(snapshot)

    await manager.connect(preview_id, websocket)
    await manager.broadcast(preview_id, message)

    websocket.send_json.assert_awaited_once_with(
        message.model_dump()
    )