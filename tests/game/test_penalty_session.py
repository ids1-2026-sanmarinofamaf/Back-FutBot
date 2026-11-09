import asyncio
from unittest.mock import Mock

import pytest

from app.game import penalty_session as session_module
from app.game.penalties import PenaltyShootout, PenaltySide
from app.game.penalty_session import PenaltySession


@pytest.fixture
def clock(monkeypatch):
    current_time = Mock(return_value=100.0)
    monkeypatch.setattr(session_module, "monotonic", current_time)
    return current_time


@pytest.fixture
def session(clock):
    shootout = PenaltyShootout(
        club_a_id=10,
        club_b_id=20,
        kickers_a=(11, 12, 13),
        kickers_b=(21, 22, 23),
        seed=123,
    )
    return PenaltySession(
        shootout=shootout,
        response_timeout=10.0,
    )


@pytest.fixture
def open_session(session):
    session.open_turn()
    return session


@pytest.mark.parametrize("timeout", [0, -1])
def test_rejects_non_positive_timeout(session, timeout):
    with pytest.raises(ValueError, match="must be positive"):
        PenaltySession(
            shootout=session.shootout,
            response_timeout=timeout,
        )


def test_reopening_turn_does_not_erase_received_choice(open_session):
    open_session.submit_choice(10, 1, PenaltySide.LEFT)
    original_deadline = open_session.deadline

    with pytest.raises(ValueError, match="already open"):
        open_session.open_turn()

    assert open_session.choices == {10: PenaltySide.LEFT}
    assert open_session.deadline == original_deadline
    assert open_session.accepting_choices is True


def test_cannot_open_turn_after_shootout_finishes(session):
    for _ in range(6):
        session.shootout.resolve_penalty(
            PenaltySide.LEFT,
            PenaltySide.LEFT,
        )

    with pytest.raises(ValueError, match="finished"):
        session.open_turn()

    assert session.accepting_choices is False


def test_event_is_set_only_after_both_clubs_respond(open_session):
    open_session.submit_choice(10, 1, PenaltySide.LEFT)

    assert open_session.choices == {10: PenaltySide.LEFT}
    assert not open_session.responses_received.is_set()
    assert open_session.shootout.turn == 0

    open_session.submit_choice(20, 1, PenaltySide.RIGHT)

    assert open_session.choices == {
        10: PenaltySide.LEFT,
        20: PenaltySide.RIGHT,
    }
    assert open_session.responses_received.is_set()
    assert open_session.shootout.turn == 0


@pytest.mark.parametrize(
    "club_id, turn, side, message",
    [
        (99, 1, PenaltySide.LEFT, "not participating"),
        (10, 0, PenaltySide.LEFT, "current penalty turn"),
        (10, 2, PenaltySide.LEFT, "current penalty turn"),
        (10, 1, "LEFT", "PenaltySide"),
        (10, 1, None, "PenaltySide"),
    ],
)
def test_invalid_choice_does_not_change_session(
    open_session,
    club_id,
    turn,
    side,
    message,
):
    with pytest.raises(ValueError, match=message):
        open_session.submit_choice(club_id, turn, side)

    assert open_session.choices == {}
    assert not open_session.responses_received.is_set()
    assert open_session.shootout.turn == 0


def test_duplicate_choice_preserves_original_response(open_session):
    open_session.submit_choice(10, 1, PenaltySide.LEFT)

    with pytest.raises(ValueError, match="already submitted"):
        open_session.submit_choice(10, 1, PenaltySide.RIGHT)

    assert open_session.choices == {10: PenaltySide.LEFT}
    assert not open_session.responses_received.is_set()


def test_choice_is_rejected_when_turn_is_closed(session):
    with pytest.raises(ValueError, match="closed"):
        session.submit_choice(10, 1, PenaltySide.LEFT)

    assert session.choices == {}


@pytest.mark.parametrize("current_time", [110.0, 111.0])
def test_choice_is_rejected_at_or_after_deadline(
    open_session,
    clock,
    current_time,
):
    clock.return_value = current_time

    with pytest.raises(ValueError, match="deadline has passed"):
        open_session.submit_choice(10, 1, PenaltySide.LEFT)

    assert open_session.choices == {}
    assert not open_session.responses_received.is_set()


@pytest.mark.asyncio
async def test_wait_resolves_when_second_response_arrives(open_session):
    open_session.submit_choice(10, 1, PenaltySide.LEFT)

    task = asyncio.create_task(open_session.wait_and_resolve())

    try:
        # Yield control so the task can start waiting.
        await asyncio.sleep(0)
        assert not task.done()

        open_session.submit_choice(20, 1, PenaltySide.RIGHT)

        result = await asyncio.wait_for(task, timeout=1.0)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert result["club_id"] == 10
    assert result["kick_side"] == "LEFT"
    assert result["save_side"] == "RIGHT"
    assert result["is_goal"] is True
    assert open_session.shootout.turn == 1
    assert open_session.accepting_choices is False

    with pytest.raises(ValueError, match="closed"):
        open_session.submit_choice(10, 1, PenaltySide.CENTER)

    with pytest.raises(ValueError, match="closed"):
        await open_session.wait_and_resolve()

    assert open_session.shootout.turn == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("responding_club", [None, 10, 20])
async def test_timeout_preserves_choices_and_randomizes_missing_ones(
    open_session,
    clock,
    responding_club,
):
    if responding_club is not None:
        open_session.submit_choice(
            responding_club,
            1,
            PenaltySide.CENTER,
        )

    # Reference shootout with the same seed and choices.
    reference = PenaltyShootout(
        club_a_id=10,
        club_b_id=20,
        kickers_a=(11, 12, 13),
        kickers_b=(21, 22, 23),
        seed=123,
    )
    expected = reference.resolve_penalty(
        kick_side=(
            PenaltySide.CENTER
            if responding_club == 10
            else None
        ),
        save_side=(
            PenaltySide.CENTER
            if responding_club == 20
            else None
        ),
    )

    clock.return_value = 110.0

    # This wait would fail if the full timeout were restarted.
    result = await asyncio.wait_for(
        open_session.wait_and_resolve(),
        timeout=1.0,
    )

    assert result == expected
    assert open_session.shootout.turn == 1
    assert open_session.accepting_choices is False


@pytest.mark.asyncio
async def test_valid_choices_survive_processing_after_deadline(
    open_session,
    clock,
):
    open_session.submit_choice(10, 1, PenaltySide.LEFT)
    open_session.submit_choice(20, 1, PenaltySide.RIGHT)

    # Both responses arrived on time; only their processing is delayed.
    clock.return_value = 111.0

    result = await open_session.wait_and_resolve()

    assert result["kick_side"] == "LEFT"
    assert result["save_side"] == "RIGHT"
    assert result["is_goal"] is True


@pytest.mark.asyncio
async def test_next_turn_clears_responses_and_reverses_roles(
    open_session,
    clock,
):
    open_session.submit_choice(10, 1, PenaltySide.LEFT)
    open_session.submit_choice(20, 1, PenaltySide.RIGHT)
    await open_session.wait_and_resolve()

    clock.return_value = 103.0
    open_session.open_turn()

    assert open_session.deadline == 113.0
    assert open_session.choices == {}
    assert not open_session.responses_received.is_set()

    # A delayed response from the previous turn must be rejected.
    with pytest.raises(ValueError, match="current penalty turn"):
        open_session.submit_choice(10, 1, PenaltySide.CENTER)

    open_session.submit_choice(10, 2, PenaltySide.LEFT)
    open_session.submit_choice(20, 2, PenaltySide.RIGHT)

    result = await open_session.wait_and_resolve()

    assert result["turn"] == 2
    assert result["club_id"] == 20
    assert result["kicker"] == 21
    assert result["kick_side"] == "RIGHT"
    assert result["save_side"] == "LEFT"


@pytest.mark.asyncio
async def test_wait_requires_open_turn(session):
    with pytest.raises(ValueError, match="closed"):
        await session.wait_and_resolve()

    assert session.shootout.turn == 0


@pytest.mark.asyncio
async def test_cancellation_closes_turn_without_resolving(open_session):
    open_session.submit_choice(10, 1, PenaltySide.LEFT)
    random_state = open_session.shootout._rng.getstate()

    task = asyncio.create_task(open_session.wait_and_resolve())

    try:
        await asyncio.sleep(0)
        assert not task.done()

        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    assert open_session.accepting_choices is False
    assert open_session.shootout.turn == 0
    assert open_session.shootout.score_a == 0
    assert open_session.shootout.score_b == 0
    assert open_session.shootout._rng.getstate() == random_state
