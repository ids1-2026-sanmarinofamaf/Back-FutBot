from unittest.mock import MagicMock, Mock, call, AsyncMock

import pytest

from app import main

from app.services import startup_service


@pytest.mark.parametrize(
    "league_ids",
    [
        [10, 20],
        [],
    ],
    ids=["started_leagues", "no_started_leagues"],
)
def test_recover_interrupted_leagues(monkeypatch, league_ids):
    db = Mock()
    session = MagicMock()
    session.__enter__.return_value = db
    session_factory = Mock(return_value=session)

    get_ids = Mock(return_value=league_ids)
    start_runner = Mock()

    timeline = Mock()
    timeline.attach_mock(session.__exit__, "exit_session")
    timeline.attach_mock(start_runner, "start_runner")

    monkeypatch.setattr(
        startup_service,
        "SessionLocal",
        session_factory,
    )
    monkeypatch.setattr(
        startup_service.league_repository,
        "get_started_leagues_ids",
        get_ids,
    )
    monkeypatch.setattr(
        startup_service,
        "start_league_runner",
        start_runner,
    )

    startup_service.recover_interrupted_leagues()

    session_factory.assert_called_once_with()
    session.__enter__.assert_called_once_with()
    get_ids.assert_called_once_with(db)

    expected_calls = [call.exit_session(None, None, None)]
    expected_calls.extend(
        call.start_runner(league_id)
        for league_id in league_ids
    )

    assert timeline.mock_calls == expected_calls


@pytest.mark.asyncio
async def test_lifespan_recovers_leagues_after_initializing_pool(monkeypatch):
    engine = MagicMock()
    recover_games = Mock()
    initialize_pool = Mock()
    recover_leagues = Mock()
    stop_leagues = AsyncMock()
    stop_matches = AsyncMock()
    shutdown_pool = Mock()

    timeline = Mock()
    timeline.attach_mock(initialize_pool, "initialize_pool")
    timeline.attach_mock(recover_leagues, "recover_leagues")
    timeline.attach_mock(stop_leagues, "stop_leagues")
    timeline.attach_mock(stop_matches, "stop_matches")
    timeline.attach_mock(shutdown_pool, "shutdown_pool")

    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "recover_interrupted_games", recover_games)
    monkeypatch.setattr(main, "initialize_worker_pool", initialize_pool)
    monkeypatch.setattr(main, "recover_interrupted_leagues", recover_leagues)
    monkeypatch.setattr(main, "stop_league_runners", stop_leagues)
    monkeypatch.setattr(main, "stop_running_matches", stop_matches)
    monkeypatch.setattr(main, "shutdown_worker_pool", shutdown_pool)

    async with main.lifespan(main.app):
        assert timeline.mock_calls == [
            call.initialize_pool(),
            call.recover_leagues(),
        ]

    assert timeline.mock_calls == [
        call.initialize_pool(),
        call.recover_leagues(),
        call.stop_leagues(),
        call.stop_matches(),
        call.shutdown_pool(),
    ]

    recover_games.assert_called_once_with()
    stop_leagues.assert_awaited_once_with()
    stop_matches.assert_awaited_once_with()
    engine.dispose.assert_called_once_with()