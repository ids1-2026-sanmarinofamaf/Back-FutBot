import asyncio

from functools import partial
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch, call

import pytest

from app.game.models.match import MatchState
from app.game.preview_runner import PreviewRunner
from app.schemas.behavior_preview import BehaviorPreviewFinishedMessage


async def execute_tick_and_stop(
    preview_id,
    preview,
    runner
    ):
    await PreviewRunner.execute_tick(runner, preview_id, preview)

    if preview.current_tick == 2:
        runner.stop()


async def execute_tick_and_signal(
    preview_id,
    preview,
    runner,
    event,
):
    await PreviewRunner.execute_tick(runner, preview_id, preview)
    event.set()


async def check_state_and_advance(preview_id,preview):
    assert preview.state == MatchState.IN_PROGRESS
    preview.current_tick += 1


async def fake_wait_for(awaitable, timeout):
    awaitable.close()
    raise asyncio.TimeoutError


def snapshot_for_tick(preview):
    return {"tick": preview.current_tick}


def identity(value):
    return value


@pytest.fixture
def coordinator():
    coordinator = Mock()
    coordinator.get_actions.return_value = {1: Mock()}
    return coordinator


@pytest.fixture
def engine():
    return Mock()


@pytest.fixture
def runner(coordinator, engine):
    return PreviewRunner(
        behavior_coordinator=coordinator,
        game_engine=engine,
    )


@pytest.fixture
def preview():
    preview = Mock()
    preview.state = MatchState.NOT_STARTED
    preview.current_tick = 0
    preview.duration_ticks = 3
    preview.snapshot.return_value = Mock()

    return preview


@pytest.fixture
def preview_id():
    return uuid4()


@pytest.fixture(autouse=True)
def mock_preview_websocket():
    with (
        patch(
            "app.game.preview_runner.build_match_state_message"
        ) as build_message,
        patch(
            "app.game.preview_runner.preview_connection_manager.broadcast",
            new_callable=AsyncMock,
        ) as broadcast,
        patch(
            "app.game.preview_runner.preview_connection_manager.close_preview_connection",
            new_callable=AsyncMock,
        ) as close,
    ):
        yield build_message, broadcast, close


@pytest.mark.asyncio
async def test_execute_tick_advances_one_tick(
    runner,
    preview,
    preview_id,
    coordinator,
    engine,
):
    await runner.execute_tick(preview_id, preview)

    assert preview.current_tick == 1

    coordinator.get_actions.assert_called_once()
    engine.step.assert_called_once()


@pytest.mark.asyncio
async def test_execute_tick_passes_same_snapshot_to_engine(
    runner,
    preview,
    preview_id,
    coordinator,
    engine,
):
    snapshot = preview.snapshot.return_value
    actions = coordinator.get_actions.return_value

    await runner.execute_tick(preview_id, preview)

    coordinator.get_actions.assert_called_once_with(snapshot)

    engine.step.assert_called_once_with(
        preview,
        snapshot,
        actions,
    )


@pytest.mark.asyncio
async def test_execute_tick_propagates_engine_error(
    runner,
    preview,
    preview_id,
    engine,
):
    engine.step.side_effect = RuntimeError("Engine failed")

    with pytest.raises(RuntimeError, match="Engine failed"):
        await runner.execute_tick(preview_id, preview)

    assert preview.current_tick == 0


@pytest.mark.asyncio
async def test_run_preview_executes_all_ticks(
    runner,
    preview,
    preview_id,
    coordinator,
    engine,
):
    result = await runner.run_preview(preview_id, preview)

    assert preview.current_tick == 3
    assert result is preview

    assert coordinator.get_actions.call_count == 3
    assert engine.step.call_count == 3


@pytest.mark.asyncio
async def test_run_preview_updates_state(
    runner,
    preview,
    preview_id,
):
    preview.duration_ticks = 1

    result = await runner.run_preview(preview_id, preview)

    assert result.state == MatchState.FINISHED
    assert result.current_tick == 1


@pytest.mark.asyncio
async def test_run_preview_sets_in_progress_before_first_tick(
    runner,
    preview,
    preview_id,
):
    preview.duration_ticks = 1

    runner.execute_tick = AsyncMock(
        side_effect=check_state_and_advance,
    )

    await runner.run_preview(preview_id, preview)

    assert preview.state == MatchState.FINISHED



@pytest.mark.asyncio
async def test_run_preview_rejects_invalid_initial_state(
    runner,
    preview,
    preview_id,
):
    preview.state = MatchState.IN_PROGRESS

    with pytest.raises(
        ValueError,
        match="Preview must be in NOT_STARTED state",
    ):
        await runner.run_preview(preview_id, preview)

    preview.state = MatchState.FINISHED

    with pytest.raises(
        ValueError,
        match="Preview must be in NOT_STARTED state",
    ):
        await runner.run_preview(preview_id, preview)


@pytest.mark.asyncio
@pytest.mark.parametrize("duration", [0, -1])
async def test_run_preview_rejects_invalid_duration(
    runner,
    preview,
    preview_id,
    duration,
):
    preview.duration_ticks = duration

    with pytest.raises(
        ValueError,
        match="Match duration must be positive",
    ):
        await runner.run_preview(preview_id, preview)


@pytest.mark.asyncio
async def test_stop_before_start_prevents_ticks(
    runner,
    preview,
    preview_id,
    coordinator,
    engine,
):
    runner.stop()

    result = await runner.run_preview(preview_id, preview)

    assert result.current_tick == 0
    assert result.state == MatchState.FINISHED

    coordinator.get_actions.assert_not_called()
    engine.step.assert_not_called()


@pytest.mark.asyncio
async def test_stop_during_execution(
    runner,
    preview,
    preview_id,
):
    preview.duration_ticks = 300

    runner.execute_tick = AsyncMock(
        side_effect=partial(
            execute_tick_and_stop,
            runner=runner,
        ),
    )

    result = await runner.run_preview(preview_id, preview)

    assert result.current_tick == 2
    assert result.state == MatchState.FINISHED


@pytest.mark.asyncio
async def test_stop_interrupts_wait(
    runner,
    preview,
    preview_id,
):
    preview.duration_ticks = 300

    first_tick_finished = asyncio.Event()

    runner.execute_tick = AsyncMock(
        side_effect=partial(
            execute_tick_and_signal,
            runner=runner,
            event=first_tick_finished,
        ),
    )

    task = asyncio.create_task(
        runner.run_preview(preview_id, preview)
    )

    await asyncio.wait_for(
        first_tick_finished.wait(),
        timeout=1,
    )

    runner.stop()

    result = await asyncio.wait_for(task, timeout=1)

    assert result.current_tick == 1
    assert result.state == MatchState.FINISHED


@pytest.mark.asyncio
async def test_run_preview_waits_remaining_tick_time(
    runner,
    preview,
    preview_id,
):
    preview.duration_ticks = 1

    with (
        patch(
            "app.game.preview_runner.time.monotonic",
            side_effect=[10.0, 10.02],
        ),
        patch(
            "app.game.preview_runner.asyncio.wait_for",
            new_callable=AsyncMock,
        ) as mock_wait,
    ):
        mock_wait.side_effect = fake_wait_for

        await runner.run_preview(preview_id, preview)

    mock_wait.assert_awaited_once()

    assert mock_wait.await_args.kwargs["timeout"] == pytest.approx(
        0.08
    )


@pytest.mark.asyncio
async def test_run_preview_does_not_wait_after_slow_tick(
    runner,
    preview,
    preview_id,
):
    preview.duration_ticks = 1

    with (
        patch(
            "app.game.preview_runner.time.monotonic",
            side_effect=[10.0, 10.15],
        ),
        patch(
            "app.game.preview_runner.asyncio.wait_for",
            new_callable=AsyncMock,
        ) as mock_wait,
    ):
        await runner.run_preview(preview_id, preview)

    mock_wait.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_preview_broadcasts_initial_snapshot(
    runner,
    preview,
    preview_id,
    mock_preview_websocket,
):
    preview.duration_ticks = 1

    build_message, broadcast, _ = mock_preview_websocket

    await runner.run_preview(preview_id, preview)

    build_message.assert_any_call(
        preview.snapshot.return_value
    )

    assert broadcast.await_args_list[0] == call(
        preview_id,
        build_message.return_value,
    )


@pytest.mark.asyncio
async def test_run_preview_broadcasts_after_each_tick(
    runner,
    preview,
    preview_id,
    mock_preview_websocket,
    monkeypatch,
):
    preview.duration_ticks = 3

    monkeypatch.setattr(
        "app.game.preview_runner.TIC_DURATION",
        0,
    )

    preview.snapshot.side_effect = partial(
        snapshot_for_tick,
        preview,
    )

    build_message, broadcast, _ = mock_preview_websocket

    build_message.side_effect = identity

    await runner.run_preview(preview_id, preview)

    assert preview.current_tick == 3

    assert build_message.call_count == 4

    assert broadcast.await_args_list == [
        call(preview_id, {"tick": 0}),
        call(preview_id, {"tick": 1}),
        call(preview_id, {"tick": 2}),
        call(preview_id, {"tick": 3}),
        call(
            preview_id,
            BehaviorPreviewFinishedMessage(reason="completed"),
        ),
    ]


@pytest.mark.asyncio
async def test_run_preview_broadcasts_completed_event(
    runner,
    preview,
    preview_id,
    mock_preview_websocket,
):
    preview.duration_ticks = 1

    _, broadcast, _ = mock_preview_websocket

    await runner.run_preview(preview_id, preview)

    broadcast.assert_any_await(
        preview_id,
        BehaviorPreviewFinishedMessage(reason="completed"),
    )

    assert preview.state == MatchState.FINISHED


@pytest.mark.asyncio
async def test_run_preview_broadcasts_stopped_event(
    runner,
    preview,
    preview_id,
    mock_preview_websocket,
):
    runner.stop()

    _, broadcast, _ = mock_preview_websocket

    await runner.run_preview(preview_id, preview)

    broadcast.assert_any_await(
        preview_id,
        BehaviorPreviewFinishedMessage(reason="stopped"),
    )

    assert preview.current_tick == 0
    assert preview.state == MatchState.FINISHED


@pytest.mark.asyncio
async def test_run_preview_closes_websocket_connections(
    runner,
    preview,
    preview_id,
    mock_preview_websocket,
):
    preview.duration_ticks = 1

    _, broadcast, close = mock_preview_websocket

    await runner.run_preview(preview_id, preview)

    close.assert_awaited_once_with(preview_id)

    assert broadcast.await_args_list[-1] == call(
        preview_id,
        BehaviorPreviewFinishedMessage(reason="completed"),
    )