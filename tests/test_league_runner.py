import asyncio

from types import SimpleNamespace
from unittest.mock import Mock, call, AsyncMock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import pytest

from app.database import Base

from app.models.user import User
from app.models.club import Club
from app.models.player import Player
from app.models.behavior import Behavior
from app.models.roster import Roster, Formation
from app.models.player_on_roster import PlayerOnRoster
from app.models.league import League, LeaguePrivacy, LeagueState
from app.models.league_participation import LeagueParticipation
from app.models.club_statistics import ClubStatistics
from app.models.match import Match as PersistedMatch, MatchState
from app.models.match_participation import (
    MatchRole,
    MatchParticipation as PersistedParticipation,
)

from app.game.models.match import MatchState as RuntimeMatchState
from app.game.constants import FIELD_CENTER, TICS_PER_SECOND

from app.services import league_runner
from app.services.league_runner import (
    load_round_matches,
    complete_round,
)


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

    builder = Mock(side_effect=[
        SimpleNamespace(club_id=1, roster_id=10),
        SimpleNamespace(club_id=2, roster_id=20),
    ])

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
    starter = ControlledMatchStarter()
    mock_match_execution(monkeypatch, starter)
    behaviors = {100: ["behavior_1"], 101: ["behavior_2"]}

    round_task = asyncio.create_task(
        league_runner.run_round_matches(
            matches=runtime_matches,
            behaviors_by_match=behaviors,
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
            matches=runtime_matches,
            behaviors_by_match={100: [], 101: []},
        )

    assert starter.started == [100, 101]

    assert len(starter.tasks) == 2
    assert all(task.done() for task in starter.tasks)

    assert starter.tasks[1].cancelled()
    assert starter.cancelled == [101]


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
            matches=runtime_matches,
            behaviors_by_match={100: [], 101: []},
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
            matches=runtime_matches,
            behaviors_by_match={100: [], 101: []},
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
        matches=[],
        behaviors_by_match={},
    )

    assert result == []

    starter.assert_not_called()


@pytest.fixture
def round_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    tables = [
        User.__table__,
        Club.__table__,
        Player.__table__,
        Behavior.__table__,
        Roster.__table__,
        PlayerOnRoster.__table__,
        League.__table__,
        LeagueParticipation.__table__,
        ClubStatistics.__table__,
        PersistedMatch.__table__,
        PersistedParticipation.__table__,
    ]

    Base.metadata.create_all(engine, tables=tables)

    with Session(engine) as db:
        yield db

    engine.dispose()


@pytest.fixture
def round_case(round_db):
    clubs = [
        Club(
            name=f"Club {i}",
            user=User(
                email=f"round-club-{i}@test.com",
                hash_passwd="hash",
            ),
            statistics=ClubStatistics(),
        )
        for i in range(4)
    ]

    round_db.add_all(clubs)
    round_db.flush()

    rosters = [
        Roster(
            club_id=club.id,
            formation=Formation.DEFENSIVE,
        )
        for club in clubs
    ]

    round_db.add_all(rosters)
    round_db.flush()

    league = League(
        name="Liga Test",
        match_duration=90,
        max_clubs=4,
        privacy=LeaguePrivacy.PUBLICA,
        creator_id=clubs[0].id,
        state=LeagueState.INICIADA,
        last_completed_round=0,
    )

    round_db.add(league)
    round_db.flush()

    for club, roster in zip(clubs, rosters):
        round_db.add(
            LeagueParticipation(
                league_id=league.id,
                club_id=club.id,
                roster_id=roster.id,
            )
        )

    fixtures = [
        (1001, 1, 0, 1),
        (1002, 1, 2, 3),
        (1003, 2, 0, 2),
    ]

    for order, (match_id, number, home, away) in enumerate(fixtures, 1):
        round_db.add(
            PersistedMatch(
                id=match_id,
                league_id=league.id,
                round=number,
                match_order=order,
                participations=[
                    PersistedParticipation(
                        club_id=clubs[home].id,
                        roster_id=rosters[home].id,
                        role=MatchRole.LOCAL,
                    ),
                    PersistedParticipation(
                        club_id=clubs[away].id,
                        roster_id=rosters[away].id,
                        role=MatchRole.VISITANTE,
                    ),
                ],
            )
        )

    round_db.commit()

    return SimpleNamespace(
        league_id=league.id,
        club_ids=[club.id for club in clubs],
    )


def make_completed_matches(case):
    ids = case.club_ids

    return [
        SimpleNamespace(
            match_id=1001,
            state=RuntimeMatchState.FINISHED,
            participation_a=SimpleNamespace(club_id=ids[0], goals=2),
            participation_b=SimpleNamespace(club_id=ids[1], goals=1),
        ),
        SimpleNamespace(
            match_id=1002,
            state=RuntimeMatchState.FINISHED,
            participation_a=SimpleNamespace(club_id=ids[2], goals=0),
            participation_b=SimpleNamespace(club_id=ids[3], goals=0),
        ),
    ]


def assert_round_unmodified(db, case):
    db.expire_all()

    league = db.get(League, case.league_id)
    assert league.last_completed_round == 0

    for match_id in (1001, 1002):
        match = db.get(PersistedMatch, match_id)
        assert match.state == MatchState.POR_COMENZAR
        assert match.home_goals is None
        assert match.away_goals is None

    for club_id in case.club_ids:
        participation = db.get(
            LeagueParticipation,
            (case.league_id, club_id),
        )
        assert participation.matches_played == 0
        assert participation.points == 0


def test_complete_round_persists_results_and_standings(
    round_db,
    round_case,
):
    matches = make_completed_matches(round_case)

    complete_round(
        round_db,
        round_case.league_id,
        1,
        matches,
        is_last_round=False,
    )

    round_db.expire_all()

    first = round_db.get(PersistedMatch, 1001)
    second = round_db.get(PersistedMatch, 1002)

    assert (first.home_goals, first.away_goals) == (2, 1)
    assert (second.home_goals, second.away_goals) == (0, 0)
    assert first.state == MatchState.FINALIZADO
    assert second.state == MatchState.FINALIZADO

    expected_points = [3, 0, 1, 1]

    for club_id, points in zip(round_case.club_ids, expected_points):
        participation = round_db.get(
            LeagueParticipation,
            (round_case.league_id, club_id),
        )
        statistics = round_db.get(ClubStatistics, club_id)

        assert participation.points == points
        assert participation.matches_played == 1
        assert statistics.total_points == points
        assert statistics.matches_played == 1

    league = round_db.get(League, round_case.league_id)
    assert league.last_completed_round == 1
    assert league.break_ends_at is not None


def test_complete_round_private_league_skips_global_statistics(
    round_db,
    round_case,
):
    league = round_db.get(League, round_case.league_id)
    league.privacy = LeaguePrivacy.PRIVADA
    league.password_hash = "hashed-password"
    round_db.commit()

    complete_round(
        round_db,
        round_case.league_id,
        1,
        make_completed_matches(round_case),
        is_last_round=False,
    )

    round_db.expire_all()

    winner = round_case.club_ids[0]

    participation = round_db.get(
        LeagueParticipation,
        (round_case.league_id, winner),
    )
    statistics = round_db.get(ClubStatistics, winner)

    assert participation.points == 3
    assert participation.matches_played == 1

    assert statistics.total_points == 0
    assert statistics.matches_played == 0


def test_complete_round_rolls_back_on_statistics_error(
    round_db,
    round_case,
):
    # The second match will fail when updating global statistics.
    failing_club_id = round_case.club_ids[2]

    round_db.delete(
        round_db.get(ClubStatistics, failing_club_id)
    )
    round_db.commit()

    with pytest.raises(LookupError):
        complete_round(
            round_db,
            round_case.league_id,
            1,
            make_completed_matches(round_case),
            is_last_round=False,
        )

    assert_round_unmodified(round_db, round_case)

    # Even statistics already updated for the first match
    # must be rolled back.
    first_club = round_case.club_ids[0]
    statistics = round_db.get(ClubStatistics, first_club)

    assert statistics.matches_played == 0
    assert statistics.total_points == 0


def test_complete_round_cannot_be_confirmed_twice(
    round_db,
    round_case,
):
    matches = make_completed_matches(round_case)

    complete_round(
        round_db,
        round_case.league_id,
        1,
        matches,
        is_last_round=False,
    )

    with pytest.raises(ValueError, match="Invalid round"):
        complete_round(
            round_db,
            round_case.league_id,
            1,
            matches,
            is_last_round=False,
        )

    round_db.expire_all()

    winner = round_case.club_ids[0]
    participation = round_db.get(
        LeagueParticipation,
        (round_case.league_id, winner),
    )

    assert participation.matches_played == 1
    assert participation.points == 3


def test_complete_round_rejects_unfinished_match(
    round_db,
    round_case,
):
    matches = make_completed_matches(round_case)
    matches[1].state = RuntimeMatchState.IN_PROGRESS

    with pytest.raises(ValueError, match="has not finished"):
        complete_round(
            round_db,
            round_case.league_id,
            1,
            matches,
            is_last_round=False,
        )

    assert_round_unmodified(round_db, round_case)


@pytest.mark.parametrize("invalid_input", [
    "missing",
    "duplicate",
    "incorrect_id",
    "empty",
])
def test_complete_round_rejects_incorrect_fixture(
    round_db,
    round_case,
    invalid_input,
):
    matches = make_completed_matches(round_case)

    if invalid_input == "missing":
        matches.pop()
    elif invalid_input == "duplicate":
        matches.append(matches[0])
    elif invalid_input == "incorrect_id":
        matches[1].match_id = 9999
    else:
        matches = []

    with pytest.raises(
        ValueError,
        match="Round matches do not match the fixture",
    ):
        complete_round(
            round_db,
            round_case.league_id,
            1,
            matches,
            is_last_round=False,
        )

    assert_round_unmodified(round_db, round_case)


@pytest.mark.parametrize("invalid_score", [-1, -5])
def test_complete_round_rejects_negative_goals(
    round_db,
    round_case,
    invalid_score,
):
    matches = make_completed_matches(round_case)
    matches[1].participation_a.goals = invalid_score

    with pytest.raises(ValueError, match="Invalid score"):
        complete_round(
            round_db,
            round_case.league_id,
            1,
            matches,
            is_last_round=False,
        )

    assert_round_unmodified(round_db, round_case)


def test_complete_round_last_round_has_no_break(
    round_db,
    round_case,
):
    # Remove the next round, making round 1 the last one.
    round_db.delete(round_db.get(PersistedMatch, 1003))
    round_db.commit()

    complete_round(
        round_db,
        round_case.league_id,
        1,
        make_completed_matches(round_case),
        is_last_round=True,
    )

    round_db.expire_all()

    league = round_db.get(League, round_case.league_id)

    assert league.last_completed_round == 1
    assert league.break_ends_at is None


@pytest.mark.parametrize(
    "state",
    [
        LeagueState.POR_COMENZAR,
        LeagueState.FINALIZADA,
    ],
)
def test_complete_round_rejects_inactive_league(
    round_db,
    round_case,
    state,
):
    league = round_db.get(League, round_case.league_id)
    league.state = state
    round_db.commit()

    with pytest.raises(ValueError, match="League is not in progress"):
        complete_round(
            round_db,
            round_case.league_id,
            1,
            make_completed_matches(round_case),
            is_last_round=False,
        )

    assert_round_unmodified(round_db, round_case)


def make_second_round_matches(case):
    return [
        SimpleNamespace(
            match_id=1003,
            state=RuntimeMatchState.FINISHED,
            participation_a=SimpleNamespace(
                club_id=case.club_ids[0],
                goals=0,
            ),
            participation_b=SimpleNamespace(
                club_id=case.club_ids[2],
                goals=2,
            ),
        ),
    ]


@pytest.mark.asyncio
async def test_run_league_executes_rounds(monkeypatch, round_db, round_case):
    first_round = make_completed_matches(round_case)
    second_round = make_second_round_matches(round_case)
    build = Mock(side_effect=[first_round, second_round])
    execute = AsyncMock()
    sleep = AsyncMock()

    monkeypatch.setattr(league_runner, "SessionLocal", sessionmaker(bind=round_db.bind))
    monkeypatch.setattr(league_runner, "build_round_matches", build)
    monkeypatch.setattr(league_runner, "load_match_behaviors", Mock(return_value=[]))
    monkeypatch.setattr(league_runner, "run_round_matches", execute)
    monkeypatch.setattr(league_runner.asyncio, "sleep", sleep)

    await league_runner.run_league(round_case.league_id)

    assert execute.await_count == 2
    assert execute.await_args_list[0].kwargs["matches"] is first_round
    assert execute.await_args_list[1].kwargs["matches"] is second_round
    assert execute.await_args_list[0].kwargs["behaviors_by_match"] == {1001: [], 1002: []}
    assert execute.await_args_list[1].kwargs["behaviors_by_match"] == {1003: []}
    sleep.assert_awaited_once()
    assert 0 < sleep.await_args.args[0] <= league_runner.ROUND_BREAK_SECONDS

    round_db.expire_all()
    league = round_db.get(League, round_case.league_id)
    assert league.last_completed_round == 2
    assert league.state == LeagueState.FINALIZADA
    assert league.break_ends_at is None
    assert all(
        round_db.get(PersistedMatch, match_id).state == MatchState.FINALIZADO
        for match_id in (1001, 1002, 1003)
    )


@pytest.mark.asyncio
async def test_run_league_resumes_pending_round(monkeypatch, round_db, round_case):
    complete_round(
        round_db,
        round_case.league_id,
        1,
        make_completed_matches(round_case),
        is_last_round=False,
    )
    second_round = make_second_round_matches(round_case)
    build = Mock(return_value=second_round)
    execute = AsyncMock()
    sleep = AsyncMock()

    monkeypatch.setattr(league_runner, "SessionLocal", sessionmaker(bind=round_db.bind))
    monkeypatch.setattr(league_runner, "build_round_matches", build)
    monkeypatch.setattr(league_runner, "load_match_behaviors", Mock(return_value=[]))
    monkeypatch.setattr(league_runner, "run_round_matches", execute)
    monkeypatch.setattr(league_runner.asyncio, "sleep", sleep)

    await league_runner.run_league(round_case.league_id)

    build.assert_called_once()
    assert [match.id for match in build.call_args.args[1]] == [1003]
    execute.assert_awaited_once()
    sleep.assert_awaited_once()

    round_db.expire_all()
    league = round_db.get(League, round_case.league_id)
    assert league.last_completed_round == 2
    assert league.state == LeagueState.FINALIZADA
    first_round_club = round_db.get(
        LeagueParticipation,
        (round_case.league_id, round_case.club_ids[1]),
    )

    assert first_round_club.matches_played == 1
