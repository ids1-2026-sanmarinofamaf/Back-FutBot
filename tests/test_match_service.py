"""
Tests for the lifecycle of the shared behavior worker pool.
"""

import asyncio
import threading
import time

from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, call

import pytest

from app.services import match_service


@pytest.fixture
def isolated_match_service(monkeypatch):
    monkeypatch.setattr(match_service, "_worker_pool", None)
    monkeypatch.setattr(match_service, "_running_match_tasks", set())
    monkeypatch.setattr(match_service, "register_match", Mock())
    monkeypatch.setattr(match_service, "remove_match", Mock())


def make_match(match_id: int):
    return SimpleNamespace(match_id=match_id)


@pytest.mark.asyncio
async def test_two_matches_use_one_shared_pool(
    isolated_match_service,
    monkeypatch,
):
    pool = Mock()
    pool_factory = Mock(return_value=pool)
    coordinator_factory = Mock()
    runner = SimpleNamespace(run_match=AsyncMock())

    monkeypatch.setattr(match_service, "BehaviorWorkerPool", pool_factory)
    monkeypatch.setattr(match_service, "BehaviorCoordinator", coordinator_factory)
    monkeypatch.setattr(match_service, "MatchRunner", Mock(return_value=runner))

    match_service.initialize_worker_pool()
    match_service.initialize_worker_pool()

    match_service.start_match(make_match(10), [])
    match_service.start_match(make_match(11), [])

    await asyncio.gather(*tuple(match_service._running_match_tasks))

    pool_factory.assert_called_once_with(size=6, timeout_ms=100)
    assert pool.register_match.call_args_list == [call(10, []), call(11, [])]
    assert coordinator_factory.call_args_list == [
        call(pool, match_id=10),
        call(pool, match_id=11),
    ]
    pool.shutdown.assert_not_called()


@pytest.mark.asyncio
async def test_finishing_one_match_does_not_stop_the_other(
    isolated_match_service,
    monkeypatch,
):
    pool = Mock()
    monkeypatch.setattr(match_service, "_worker_pool", pool)

    second_match_started = asyncio.Event()
    finish_second_match = asyncio.Event()

    async def run_match(match):
        if match.match_id == 11:
            second_match_started.set()
            await finish_second_match.wait()
        return match

    runner = SimpleNamespace(run_match=run_match)

    monkeypatch.setattr(
        match_service,
        "MatchRunner",
        Mock(return_value=runner),
    )

    # Start the match that will remain running.
    match_service.start_match(make_match(11), [])

    second_task = next(
        iter(match_service._running_match_tasks)
    )

    # Start the match that finishes immediately.
    match_service.start_match(make_match(10), [])

    first_task = next(
        task
        for task in match_service._running_match_tasks
        if task is not second_task
    )

    try:
        await asyncio.wait_for(
            second_match_started.wait(),
            timeout=2,
        )

        # Wait until the first match finishes its cleanup.
        await asyncio.wait_for(first_task, timeout=2)

        pool.release_match.assert_called_once_with(10)
        match_service.remove_match.assert_called_once_with(10)

        # The other match must still be running.
        assert not second_task.done()
        pool.shutdown.assert_not_called()

    finally:
        finish_second_match.set()

        await asyncio.gather(
            first_task,
            second_task,
            return_exceptions=True,
        )

    assert pool.release_match.call_args_list == [
        call(10),
        call(11),
    ]

    pool.shutdown.assert_not_called()


@pytest.mark.asyncio
async def test_application_shutdown_closes_shared_pool(
    isolated_match_service,
    monkeypatch,
):
    main_module = import_module("app.main")
    pool = Mock()
    pool_factory = Mock(return_value=pool)

    monkeypatch.setattr(match_service, "BehaviorWorkerPool", pool_factory)
    recover = Mock()
    connect = MagicMock()
    dispose = Mock()
    monkeypatch.setattr(main_module, "recover_interrupted_games", recover)
    monkeypatch.setattr(main_module.engine, "connect", connect)
    monkeypatch.setattr(main_module.engine, "dispose", dispose)

    async with main_module.lifespan(main_module.app):
        assert match_service._worker_pool is pool
        pool.shutdown.assert_not_called()

    pool_factory.assert_called_once_with(size=6, timeout_ms=100)
    pool.shutdown.assert_called_once_with()
    assert match_service._worker_pool is None
    recover.assert_called_once_with()
    dispose.assert_called_once_with()


def test_start_match_releases_resources_if_initialization_fails(
    monkeypatch,
):
    match = SimpleNamespace(match_id=50)
    behaviors = []

    worker_pool = MagicMock()

    register_match = MagicMock()
    remove_match = MagicMock()

    monkeypatch.setattr(
        match_service,
        "_worker_pool",
        worker_pool,
    )

    monkeypatch.setattr(
        match_service,
        "register_match",
        register_match,
    )

    monkeypatch.setattr(
        match_service,
        "remove_match",
        remove_match,
    )

    # Simulate a failure after registering the match in the pool.
    monkeypatch.setattr(
        match_service,
        "BehaviorCoordinator",
        MagicMock(
            side_effect=RuntimeError("Initialization failed")
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="Initialization failed",
    ):
        match_service.start_match(
            match=match,
            behaviors=behaviors,
        )

    register_match.assert_called_once_with(match)

    worker_pool.register_match.assert_called_once_with(
        50,
        behaviors,
    )

    worker_pool.release_match.assert_called_once_with(50)

    remove_match.assert_called_once_with(50)


@pytest.mark.asyncio
async def test_stop_running_matches_cancels_all_tasks(
    monkeypatch,
):
    cleaned_up = []

    started_1 = asyncio.Event()
    started_2 = asyncio.Event()

    async def fake_match(match_id, started):
        started.set()

        try:
            await asyncio.Event().wait()
        finally:
            cleaned_up.append(match_id)

    task_1 = asyncio.create_task(
        fake_match(1, started_1)
    )

    task_2 = asyncio.create_task(
        fake_match(2, started_2)
    )

    tasks = {task_1, task_2}

    monkeypatch.setattr(
        match_service,
        "_running_match_tasks",
        tasks,
    )

    try:
        # Ensure both tasks have started.
        await asyncio.wait_for(
            asyncio.gather(
                started_1.wait(),
                started_2.wait(),
            ),
            timeout=2,
        )

        await match_service.stop_running_matches()

        assert task_1.done()
        assert task_2.done()

        assert task_1.cancelled()
        assert task_2.cancelled()

        assert sorted(cleaned_up) == [1, 2]

    finally:
        # Avoid leaving tasks running if the test fails.
        for task in tasks:
            task.cancel()

        await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )


@pytest.mark.asyncio
async def test_cancelling_match_does_not_block_event_loop(
    isolated_match_service,
):
    worker_lock = threading.Lock()
    actions_started = threading.Event()
    finish_actions = threading.Event()
    release_started = threading.Event()

    def get_actions():
        with worker_lock:
            actions_started.set()
            finish_actions.wait(timeout=2)

    async def run_match(match):
        await asyncio.to_thread(get_actions)

    def release_match(match_id):
        release_started.set()
        with worker_lock:
            pass

    pool = Mock()
    pool.release_match.side_effect = release_match

    runner = SimpleNamespace(run_match=run_match)
    match = make_match(10)

    task = asyncio.create_task(
        match_service._run_match(
            match=match,
            runner=runner,
            worker_pool=pool,
        )
    )

    try:
        assert await asyncio.to_thread(
            actions_started.wait, 1
        )

        # The asyncio task is cancelled, but get_actions
        # continues running in another thread.
        task.cancel()

        # Safety net to avoid a permanent deadlock
        # if release_match blocks the event loop.
        timer = threading.Timer(0.5, finish_actions.set)
        timer.start()

        try:
            start = time.monotonic()

            await asyncio.sleep(0.02)

            elapsed = time.monotonic() - start

            # The event loop must remain responsive.
            assert elapsed < 0.25
            assert not task.done()

        finally:
            finish_actions.set()
            timer.cancel()

        await asyncio.wait_for(
            asyncio.gather(task, return_exceptions=True),
            timeout=3,
        )

        pool.release_match.assert_called_once_with(10)
        match_service.remove_match.assert_called_once_with(10)

    finally:
        finish_actions.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)