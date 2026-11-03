import asyncio

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from app.models.match_participation import MatchRole
from app.game.constants import FIELD_CENTER, TICS_PER_SECOND

from app.services import league_runner
from app.services.league_runner import load_round_matches


class ControlledMatchStarter:
    """Simulate match tasks with controlled completion and failures."""

    def __init__(
        self,
        expected_matches=2,
        fail_during_run=None,
        fail_during_start=None,
    ):
        self.expected_matches = expected_matches
        self.fail_during_run = fail_during_run
        self.fail_during_start = fail_during_start

        self.all_started = asyncio.Event()
        self.release = asyncio.Event()

        self.calls = []
        self.started = []
        self.cancelled = []
        self.tasks = []

    def __call__(self, *, match, behaviors):
        if match.match_id == self.fail_during_start:
            raise RuntimeError("Cannot start match")

        self.calls.append(
            call(match=match, behaviors=behaviors)
        )

        task = asyncio.create_task(
            self._simulate_match(match.match_id)
        )

        self.tasks.append(task)

        return task

    async def _simulate_match(self, match_id):
        self.started.append(match_id)

        if len(self.started) == self.expected_matches:
            self.all_started.set()

        try:
            await self.all_started.wait()

            if match_id == self.fail_during_run:
                raise RuntimeError("Match failed")

            await self.release.wait()

        except asyncio.CancelledError:
            self.cancelled.append(match_id)
            raise


@pytest.fixture
def runtime_matches():
    return [
        SimpleNamespace(match_id=100),
        SimpleNamespace(match_id=101),
    ]


def mock_match_execution(
    monkeypatch,
    starter,
    behavior_loader=None,
):
    if behavior_loader is None:
        behavior_loader = Mock(return_value=[])

    monkeypatch.setattr(
        league_runner,
        "start_match_task",
        starter,
    )

    monkeypatch.setattr(
        league_runner,
        "load_match_behaviors",
        behavior_loader,
    )

    return behavior_loader


def test_load_round_matches_filters_and_orders():
    db = Mock()

    matches = [Mock(id=10), Mock(id=11)]
    db.scalars.return_value.all.return_value = matches

    result = load_round_matches(
        db=db,
        league_id=5,
        round_number=2,
    )

    assert result == matches

    stmt = db.scalars.call_args.args[0]

    sql = str(
        stmt.compile(
            compile_kwargs={"literal_binds": True}
        )
    )

    assert "matches.league_id = 5" in sql
    assert "matches.round = 2" in sql
    assert "ORDER BY matches.match_order" in sql


def test_load_round_matches_returns_empty_list():
    db = Mock()
    db.scalars.return_value.all.return_value = []

    result = load_round_matches(
        db=db,
        league_id=5,
        round_number=3,
    )

    assert result == []


def test_build_round_matches(monkeypatch):
    db = Mock()

    home_roster = SimpleNamespace(id=10, club_id=1)
    away_roster = SimpleNamespace(id=20, club_id=2)

    home = SimpleNamespace(
        role=MatchRole.LOCAL,
        roster=home_roster,
    )
    away = SimpleNamespace(
        role=MatchRole.VISITANTE,
        roster=away_roster,
    )

    persisted_match = SimpleNamespace(
        id=100,
        participations=[away, home],  # Reversed intentionally
    )

    def build_participation(db, roster, mirror_position):
        return SimpleNamespace(
            club_id=roster.club_id,
            roster_id=roster.id,
        )

    builder = Mock(side_effect=build_participation)

    monkeypatch.setattr(
        league_runner,
        "create_match_participation",
        builder,
    )

    result = league_runner.build_round_matches(
        db=db,
        matches=[persisted_match],
        duration_seconds=90,
    )

    assert len(result) == 1

    match = result[0]

    assert match.match_id == 100
    assert match.participation_a.club_id == 1
    assert match.participation_b.club_id == 2

    assert match.duration_ticks == 90 * TICS_PER_SECOND
    assert match.ball.position == FIELD_CENTER
    assert match.ball.velocity == (0.0, 0.0)

    builder.assert_has_calls([
        call(
            db=db,
            roster=home_roster,
            mirror_position=False,
        ),
        call(
            db=db,
            roster=away_roster,
            mirror_position=True,
        ),
    ])


@pytest.mark.parametrize(
    "roles",
    [
        [MatchRole.LOCAL],
        [MatchRole.LOCAL, MatchRole.LOCAL],
        [MatchRole.VISITANTE, MatchRole.VISITANTE],
    ],
)
def test_build_round_matches_rejects_invalid_participations(roles):
    db = Mock()

    persisted_match = SimpleNamespace(
        id=100,
        participations=[
            SimpleNamespace(role=role)
            for role in roles
        ],
    )

    with pytest.raises(
        ValueError,
        match="must have one home and one away club",
    ):
        league_runner.build_round_matches(
            db=db,
            matches=[persisted_match],
            duration_seconds=90,
        )


@pytest.mark.asyncio
async def test_run_round_matches_concurrently(
    monkeypatch,
    runtime_matches,
):
    db = Mock()
    starter = ControlledMatchStarter()

    behavior_loader = Mock(
        side_effect=[
            ["behavior_1"],
            ["behavior_2"],
        ]
    )

    mock_match_execution(
        monkeypatch,
        starter,
        behavior_loader,
    )

    round_task = asyncio.create_task(
        league_runner.run_round_matches(
            db=db,
            matches=runtime_matches,
        )
    )

    try:
        await asyncio.wait_for(
            starter.all_started.wait(),
            timeout=2,
        )

        # Both matches started, but the round is still running.
        assert starter.started == [100, 101]
        assert not round_task.done()

        behavior_loader.assert_has_calls([
            call(db=db, match=runtime_matches[0]),
            call(db=db, match=runtime_matches[1]),
        ])

        assert starter.calls == [
            call(
                match=runtime_matches[0],
                behaviors=["behavior_1"],
            ),
            call(
                match=runtime_matches[1],
                behaviors=["behavior_2"],
            ),
        ]

        starter.release.set()

        result = await round_task

        assert result is runtime_matches
        assert all(task.done() for task in starter.tasks)
        assert all(not task.cancelled() for task in starter.tasks)

    finally:
        starter.release.set()
        if not round_task.done():
            round_task.cancel()
        await asyncio.gather(round_task, return_exceptions=True)


@pytest.mark.asyncio
async def test_run_round_matches_cancels_others_on_failure(
    monkeypatch,
    runtime_matches,
):
    starter = ControlledMatchStarter(
        fail_during_run=100,
    )

    mock_match_execution(monkeypatch, starter)

    with pytest.raises(
        RuntimeError,
        match="Match failed",
    ):
        await league_runner.run_round_matches(
            db=Mock(),
            matches=runtime_matches,
        )

    assert starter.started == [100, 101]

    assert len(starter.tasks) == 2
    assert all(task.done() for task in starter.tasks)

    assert starter.tasks[1].cancelled()
    assert starter.cancelled == [101]


@pytest.mark.asyncio
async def test_run_round_matches_cancels_tasks_if_behavior_loading_fails(
    monkeypatch,
    runtime_matches,
):
    starter = ControlledMatchStarter(
        expected_matches=1,
    )

    behavior_loader = Mock(
        side_effect=[
            [],
            RuntimeError("Cannot load behaviors"),
        ]
    )

    mock_match_execution(
        monkeypatch,
        starter,
        behavior_loader,
    )

    with pytest.raises(
        RuntimeError,
        match="Cannot load behaviors",
    ):
        await league_runner.run_round_matches(
            db=Mock(),
            matches=runtime_matches,
        )

    assert len(starter.tasks) == 1
    assert starter.tasks[0].cancelled()


@pytest.mark.asyncio
async def test_run_round_matches_cancels_tasks_if_start_fails(
    monkeypatch,
    runtime_matches,
):
    starter = ControlledMatchStarter(
        expected_matches=1,
        fail_during_start=101,
    )

    mock_match_execution(monkeypatch, starter)

    with pytest.raises(
        RuntimeError,
        match="Cannot start match",
    ):
        await league_runner.run_round_matches(
            db=Mock(),
            matches=runtime_matches,
        )

    assert len(starter.tasks) == 1
    assert starter.tasks[0].cancelled()


@pytest.mark.asyncio
async def test_run_round_matches_handles_cancellation(
    monkeypatch,
    runtime_matches,
):
    starter = ControlledMatchStarter()

    mock_match_execution(monkeypatch, starter)

    round_task = asyncio.create_task(
        league_runner.run_round_matches(
            db=Mock(),
            matches=runtime_matches,
        )
    )

    await asyncio.wait_for(
        starter.all_started.wait(),
        timeout=2,
    )

    round_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await round_task

    assert all(task.done() for task in starter.tasks)
    assert all(task.cancelled() for task in starter.tasks)
    assert set(starter.cancelled) == {100, 101}


@pytest.mark.asyncio
async def test_run_round_matches_with_empty_round(monkeypatch):
    starter = Mock()
    behavior_loader = Mock()

    mock_match_execution(
        monkeypatch,
        starter,
        behavior_loader,
    )

    result = await league_runner.run_round_matches(
        db=Mock(),
        matches=[],
    )

    assert result == []

    starter.assert_not_called()
    behavior_loader.assert_not_called()
