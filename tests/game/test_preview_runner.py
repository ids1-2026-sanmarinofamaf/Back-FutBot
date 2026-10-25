import asyncio

import pytest

from unittest.mock import Mock, AsyncMock, patch

from app.game.models.match import MatchState
from app.game.preview_runner import PreviewRunner


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


@pytest.mark.asyncio
async def test_execute_tick_advances_one_tick(
    runner,
    preview,
    coordinator,
    engine,
):
    await runner.execute_tick(preview)

    assert preview.current_tick == 1

    coordinator.get_actions.assert_called_once()
    engine.step.assert_called_once()


@pytest.mark.asyncio
async def test_execute_tick_passes_same_snapshot_to_engine(
    runner,
    preview,
    coordinator,
    engine,
):
    snapshot = preview.snapshot.return_value
    actions = coordinator.get_actions.return_value

    await runner.execute_tick(preview)

    coordinator.get_actions.assert_called_once_with(snapshot)

    engine.step.assert_called_once_with(
        preview,
        snapshot,
        actions,
    )


@pytest.mark.asyncio
async def test_run_preview_executes_all_ticks(
    runner,
    preview,
    coordinator,
    engine,
):
    result = await runner.run_preview(preview)

    assert preview.current_tick == 3
    assert result is preview

    assert coordinator.get_actions.call_count == 3
    assert engine.step.call_count == 3


@pytest.mark.asyncio
async def test_run_preview_updates_state(
    runner,
    preview,
):
    preview.duration_ticks = 1

    result = await runner.run_preview(preview)

    assert result.state == MatchState.FINISHED
    assert result.current_tick == 1


@pytest.mark.asyncio
async def test_run_preview_rejects_invalid_initial_state(
    runner,
    preview,
):
    preview.state = MatchState.IN_PROGRESS

    with pytest.raises(
        ValueError,
        match="Preview must be in NOT_STARTED state",
    ):
        await runner.run_preview(preview)

    preview.state = MatchState.FINISHED

    with pytest.raises(
        ValueError,
        match="Preview must be in NOT_STARTED state",
    ):
        await runner.run_preview(preview)


@pytest.mark.asyncio
@pytest.mark.parametrize("duration", [0, -1])
async def test_run_preview_rejects_invalid_duration(
    runner,
    preview,
    duration,
):
    preview.duration_ticks = duration

    with pytest.raises(
        ValueError,
        match="Match duration must be positive",
    ):
        await runner.run_preview(preview)


@pytest.mark.asyncio
async def test_stop_before_start_prevents_ticks(
    runner,
    preview,
    coordinator,
    engine,
):
    runner.stop()

    result = await runner.run_preview(preview)

    assert result.current_tick == 0
    assert result.state == MatchState.FINISHED

    coordinator.get_actions.assert_not_called()
    engine.step.assert_not_called()


@pytest.mark.asyncio
async def test_stop_during_execution(
    runner,
    preview,
):
    preview.duration_ticks = 300

    original_execute_tick = runner.execute_tick

    async def execute_and_stop(match):
        await original_execute_tick(match)

        if match.current_tick == 2:
            runner.stop()

    runner.execute_tick = execute_and_stop

    result = await runner.run_preview(preview)

    assert result.current_tick == 2
    assert result.state == MatchState.FINISHED


@pytest.mark.asyncio
async def test_stop_interrupts_wait(
    runner,
    preview,
    monkeypatch,
):
    preview.duration_ticks = 300

    first_tick_finished = asyncio.Event()
    original_execute_tick = runner.execute_tick

    async def execute_and_signal(match):
        await original_execute_tick(match)
        first_tick_finished.set()

    runner.execute_tick = execute_and_signal

    task = asyncio.create_task(runner.run_preview(preview))

    await asyncio.wait_for(
        first_tick_finished.wait(),
        timeout=1,
    )

    runner.stop()

    result = await asyncio.wait_for(task, timeout=1)

    assert result.current_tick == 1
    assert result.state == MatchState.FINISHED


@pytest.mark.asyncio
async def test_run_preview_sets_in_progress_before_first_tick(
    runner,
    preview,
):
    preview.duration_ticks = 1

    async def check_state(match):
        assert match.state == MatchState.IN_PROGRESS
        match.current_tick += 1

    runner.execute_tick = AsyncMock(side_effect=check_state)

    await runner.run_preview(preview)

    assert preview.state == MatchState.FINISHED


async def fake_wait_for(awaitable, timeout):
    awaitable.close()
    raise asyncio.TimeoutError


@pytest.mark.asyncio
async def test_run_preview_waits_remaining_tick_time(
    runner,
    preview,
):
    preview.duration_ticks = 1

    with( 
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

        await runner.run_preview(preview)

    assert mock_wait.await_args.kwargs["timeout"] == pytest.approx(0.08)


@pytest.mark.asyncio
async def test_run_preview_does_not_wait_after_slow_tick(
    runner,
    preview,
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
        await runner.run_preview(preview)

    mock_wait.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_tick_propagates_engine_error(
    runner,
    preview,
    engine,
):
    engine.step.side_effect = RuntimeError("Engine failed")

    with pytest.raises(RuntimeError, match="Engine failed"):
        await runner.execute_tick(preview)

    assert preview.current_tick == 0