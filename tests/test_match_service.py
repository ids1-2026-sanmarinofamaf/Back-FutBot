"""
Tests for the lifecycle of the shared behavior worker pool.
"""

import asyncio
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
    first_match_released = asyncio.Event()

    def record_release(match_id):
        if match_id == 10:
            first_match_released.set()

    pool.release_match.side_effect = record_release

    async def run_match(match):
        if match.match_id == 11:
            second_match_started.set()
            await finish_second_match.wait()
        return match

    runner = SimpleNamespace(run_match=run_match)
    monkeypatch.setattr(match_service, "MatchRunner", Mock(return_value=runner))

    match_service.start_match(make_match(11), [])
    match_service.start_match(make_match(10), [])

    try:
        await asyncio.wait_for(second_match_started.wait(), timeout=2)
        await asyncio.wait_for(first_match_released.wait(), timeout=2)

        pool.release_match.assert_called_once_with(10)
        match_service.remove_match.assert_called_once_with(10)
        pool.shutdown.assert_not_called()

    finally:
        finish_second_match.set()
        await asyncio.gather(
            *tuple(match_service._running_match_tasks),
            return_exceptions=True,
        )

    assert pool.release_match.call_args_list == [call(10), call(11)]
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
