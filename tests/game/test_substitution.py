from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.database import get_db
from app.game.models.ball import Ball
from app.game.models.match import Match, MatchState
from app.game.models.match_participation import MatchParticipation
from app.game.types import Period
from app.main import app
from conftest import make_player


@pytest.fixture
def participation(six_players):
    # create a test participation with three starters and three substitutes
    return MatchParticipation(club_id=1, roster_id=1, players=six_players)


@pytest.fixture
def active_match(six_players):
    # set up an active match with two clubs and separate player rosters
    participation_a = MatchParticipation(club_id=1, roster_id=1, players=six_players)
    participation_b = MatchParticipation(
        club_id=2,
        roster_id=2,
        players=[make_player(player_id, player_id <= 9) for player_id in range(7, 13)],
    )
    match = Match(
        match_id=12,
        participation_a=participation_a,
        participation_b=participation_b,
        ball=Ball(position=(20.0, 10.0), velocity=(0.0, 0.0)),
        duration_ticks=1000,
    )
    match.state = MatchState.IN_PROGRESS
    return match


@pytest.fixture
def api_dependencies():
    # mocks an authenticated user and database session without real database queries
    user = SimpleNamespace(id=123)
    db = MagicMock()

    def override_get_db():
        yield db

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield user, db
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_valid_request_is_saved_without_executing(participation):
    # checks that planning stores a pending substitution without executing or counting it
    participation.plan_substitution(1, 4, Period.FIRST_QUARTER)

    pending = participation.pending_substitution
    assert pending is not None
    assert (pending.player_out_id, pending.player_in_id, pending.period) == (1, 4, Period.FIRST_QUARTER)
    assert participation.last_substitution_period is None
    assert participation.get_player(1).is_on_field
    assert not participation.get_player(4).is_on_field


def test_new_valid_request_replaces_pending(participation):
    # checks that a new valid request replaces the previous pending substitution
    participation.plan_substitution(1, 4, Period.FIRST_QUARTER)
    participation.plan_substitution(2, 5, Period.FIRST_QUARTER)

    pending = participation.pending_substitution
    assert (pending.player_out_id, pending.player_in_id) == (2, 5)
    assert participation.last_substitution_period is None


@pytest.mark.parametrize(
    "player_out_id, player_in_id, message",
    [
        (99, 4, "does not belong"),
        (1, 99, "does not belong"),
        (4, 5, "Outgoing player is not on field"),
        (1, 2, "Incoming player is not a substitute"),
    ],
)
def test_invalid_request_is_rejected(
    participation, player_out_id, player_in_id, message
):
    # rejects unknown players or invalid outgoing and incoming player roles
    with pytest.raises(ValueError, match=message):
        participation.plan_substitution(
            player_out_id, player_in_id, Period.FIRST_QUARTER
        )
    assert participation.pending_substitution is None


@pytest.mark.parametrize(
    "player_out_id, player_in_id",
    [(99, 4), (1, 99), (4, 5), (1, 2)],
)
def test_invalid_request_preserves_previous_pending(
    participation, player_out_id, player_in_id
):
    # checks that an invalid request preserves the existing pending substitution
    participation.plan_substitution(1, 4, Period.FIRST_QUARTER)
    previous = participation.pending_substitution

    with pytest.raises(ValueError):
        participation.plan_substitution(
            player_out_id, player_in_id, Period.FIRST_QUARTER
        )

    assert participation.pending_substitution is previous


def test_outgoing_player_needs_starting_position(participation):
    # requires the outgoing starter to have a valid starting position
    participation.get_player(1).starting_position = None
    with pytest.raises(ValueError, match="no starting position"):
        participation.plan_substitution(1, 4, Period.FIRST_QUARTER)


def test_fourth_period_does_not_allow_substitution(participation):
    # prevents planning substitutions during the fourth period
    with pytest.raises(ValueError, match="No substitution available"):
        participation.plan_substitution(1, 4, Period.FOURTH_QUARTER)



def test_execute_without_pending_does_nothing(participation):
    # confirms that no substitution occurs when there is no pending request
    assert not participation.execute_pending_substitution(Period.FIRST_QUARTER)
    assert participation.last_substitution_period is None


def test_execution_updates_players_and_clears_pending(participation):
    # checks lineup changes, execution tracking, and pending request cleanup
    participation.plan_substitution(1, 4, Period.FIRST_QUARTER)
    assert participation.execute_pending_substitution(Period.FIRST_QUARTER)

    assert not participation.get_player(1).is_on_field
    assert participation.get_player(4).is_on_field
    assert sum(p.is_on_field for p in participation.players) == 3
    assert participation.pending_substitution is None
    assert participation.last_substitution_period == Period.FIRST_QUARTER

# checks that the incoming player inherits the current position and behavior
def test_incoming_inherits_starting_position_and_behavior(participation):
    outgoing = participation.get_player(1)
    incoming = participation.get_player(4)

    outgoing.position = (15.0, 7.0)
    outgoing.starting_position = (8.0, 5.0)

    participation.plan_substitution(1, 4, Period.FIRST_QUARTER)
    outgoing.current_behavior_id = 25

    participation.execute_pending_substitution(Period.FIRST_QUARTER)

    assert incoming.position == (8.0, 5.0)
    assert incoming.starting_position == (8.0, 5.0)
    assert incoming.current_behavior_id == 25
    assert outgoing.current_behavior_id is None


def test_incoming_keeps_own_pacss(participation):
    # ensures the incoming player retains their own PACSS attributes.
    outgoing = participation.get_player(1)
    incoming = participation.get_player(4)
    outgoing.power, outgoing.agility, outgoing.control = 90, 80, 70
    outgoing.speed, outgoing.strength = 60, 50
    incoming.power, incoming.agility, incoming.control = 10, 20, 30
    incoming.speed, incoming.strength = 40, 50

    participation.plan_substitution(1, 4, Period.FIRST_QUARTER)
    participation.execute_pending_substitution(Period.FIRST_QUARTER)

    assert (
        incoming.power,
        incoming.agility,
        incoming.control,
        incoming.speed,
        incoming.strength,
    ) == (10, 20, 30, 40, 50)

def test_execution_resets_timers(participation):
    # checks temporary penalties are reset
    outgoing = participation.get_player(1)
    incoming = participation.get_player(4)

    incoming.kick_cooldown_remaining = 3
    incoming.forced_wait_remaining = 2
    incoming.collision_penalty_remaining = 4

    participation.plan_substitution(1, 4, Period.FIRST_QUARTER)
    participation.execute_pending_substitution(Period.FIRST_QUARTER)

    assert incoming.kick_cooldown_remaining == 0
    assert incoming.forced_wait_remaining == 0
    assert incoming.collision_penalty_remaining == 0


def test_only_one_executed_substitution_per_period(participation):
    # prevents executing more than one substitution per period
    period = Period.FIRST_QUARTER
    participation.plan_substitution(1, 4, period)
    assert participation.execute_pending_substitution(period)
    assert not participation.execute_pending_substitution(period)
    with pytest.raises(ValueError, match="already executed"):
        participation.plan_substitution(2, 5, period)


def test_substitutions_are_allowed_again_in_later_periods(participation):
    # allows substitutions in later periods while enforcing the per-period limit
    for period, outgoing, incoming in (
        (Period.FIRST_QUARTER, 1, 4),
        (Period.SECOND_QUARTER, 2, 5),
        (Period.THIRD_QUARTER, 3, 6),
    ):
        participation.plan_substitution(outgoing, incoming, period)
        assert participation.execute_pending_substitution(period)

    assert {p.player_id for p in participation.players if p.is_on_field} == {4, 5, 6}
    assert participation.last_substitution_period == Period.THIRD_QUARTER


def test_pending_from_other_period_is_not_executed(participation):
    # prevents executing a pending substitution for a different period
    participation.plan_substitution(1, 4, Period.FIRST_QUARTER)
    assert not participation.execute_pending_substitution(Period.SECOND_QUARTER)
    assert participation.get_player(1).is_on_field
    assert not participation.get_player(4).is_on_field
    assert participation.last_substitution_period is None
    assert participation.pending_substitution is None  # Current implementation.




def test_only_participating_clubs_can_plan(active_match):
    # eejects substitution requests from clubs not participating in the match
    with pytest.raises(PermissionError, match="not participating"):
        active_match.plan_substitution(99, 1, 4)
    assert active_match.participation_a.pending_substitution is None
    assert active_match.participation_b.pending_substitution is None


def test_each_club_plans_and_executes_its_own_substitution(active_match):
    # checks that both clubs can execute substitutions independently
    active_match.plan_substitution(1, 1, 4)
    active_match.plan_substitution(2, 7, 10)
    active_match.close_and_execute_substitutions()

    assert not active_match.substitution_requests_open
    for participation, outgoing, incoming in (
        (active_match.participation_a, 1, 4),
        (active_match.participation_b, 7, 10),
    ):
        assert not participation.get_player(outgoing).is_on_field
        assert participation.get_player(incoming).is_on_field
        assert participation.pending_substitution is None
        assert participation.last_substitution_period == Period.FIRST_QUARTER


@pytest.mark.parametrize("state", [MatchState.NOT_STARTED, MatchState.FINISHED])
def test_cannot_plan_when_match_is_not_running(active_match, state):
    # rejects planning requests when the match is not in progress
    active_match.state = state
    with pytest.raises(ValueError, match="not in progress"):
        active_match.plan_substitution(1, 1, 4)


@pytest.mark.parametrize("state", [MatchState.NOT_STARTED, MatchState.FINISHED])
def test_cannot_execute_when_match_is_not_running(active_match, state):
    # prevents executing pending substitutions when the match is not in progress
    active_match.state = state
    with pytest.raises(ValueError, match="not in progress"):
        active_match.close_and_execute_substitutions()


def test_closed_window_rejects_planning(active_match):
    # rejects new plans after the substitution window closes
    active_match.close_and_execute_substitutions()
    with pytest.raises(ValueError, match="planning is closed"):
        active_match.plan_substitution(1, 1, 4)


def test_closing_twice_does_not_repeat_substitution(active_match):
    # checks that closing the window twice does not execute the change again
    active_match.plan_substitution(1, 1, 4)
    active_match.close_and_execute_substitutions()
    active_match.close_and_execute_substitutions()
    assert active_match.participation_a.get_player(4).is_on_field
    assert active_match.participation_a.last_substitution_period == Period.FIRST_QUARTER


def test_cannot_start_next_period_while_window_open(active_match):
    # requires the substitution window to close before advancing periods
    with pytest.raises(ValueError, match="still open"):
        active_match.start_next_period(Period.SECOND_QUARTER)


def test_cannot_skip_period(active_match):
    # rejects transitions that skip match periods
    active_match.close_and_execute_substitutions()
    with pytest.raises(ValueError, match="Invalid period transition"):
        active_match.start_next_period(Period.THIRD_QUARTER)


def test_second_period_reopens_planning(active_match):
    # checks that the second period reopens substitution planning.
    active_match.close_and_execute_substitutions()
    active_match.start_next_period(Period.SECOND_QUARTER)
    assert active_match.current_period == Period.SECOND_QUARTER
    assert active_match.substitution_requests_open
    active_match.plan_substitution(1, 1, 4)
    assert active_match.participation_a.pending_substitution.period == Period.SECOND_QUARTER


def test_fourth_period_disables_planning(active_match):
    # checks that substitution planning stays closed in the fourth period
    for period in (
        Period.SECOND_QUARTER,
        Period.THIRD_QUARTER,
        Period.FOURTH_QUARTER,
    ):
        active_match.close_and_execute_substitutions()
        active_match.start_next_period(period)

    assert active_match.current_period == Period.FOURTH_QUARTER
    assert not active_match.substitution_requests_open
    with pytest.raises(ValueError, match="planning is closed"):
        active_match.plan_substitution(1, 1, 4)


def test_match_snapshot_after_substitution(active_match):
    # checks that the match snapshot reflects the updated lineup and behavior
    active_match.plan_substitution(1, 1, 4)
    active_match.close_and_execute_substitutions()
    players = {p.player_id: p for p in active_match.snapshot().players_a}
    assert not players[1].is_on_field
    assert players[4].is_on_field
    assert players[4].current_behavior_id == 1


# checks all the http codes
def test_endpoint_valid_request_returns_204(api_dependencies):
    user, db = api_dependencies
    match = MagicMock()
    with patch("app.api.matches.get_match", return_value=match) as mock_match, patch(
        "app.api.matches.club_repository.get_by_user_id",
        return_value=SimpleNamespace(id=5),
    ) as mock_club:
        response = TestClient(app).put(
            "/live_match/12/me/3", json={"new_player": 6}
        )

    assert response.status_code == 204
    assert response.content == b""
    mock_match.assert_called_once_with(12)
    mock_club.assert_called_once_with(db, user.id)
    match.plan_substitution.assert_called_once_with(
        club_id=5, player_out_id=3, player_in_id=6
    )


def test_endpoint_returns_404_for_missing_match(api_dependencies):
    with patch("app.api.matches.get_match", return_value=None):
        response = TestClient(app).put(
            "/live_match/999/me/3", json={"new_player": 6}
        )
    assert response.status_code == 404
    assert response.json() == {"detail": "Match not found"}


def test_endpoint_returns_403_for_user_without_club(api_dependencies):
    with patch("app.api.matches.get_match", return_value=MagicMock()), patch(
        "app.api.matches.club_repository.get_by_user_id", return_value=None
    ):
        response = TestClient(app).put(
            "/live_match/12/me/3", json={"new_player": 6}
        )
    assert response.status_code == 403
    assert response.json() == {"detail": "User has no club"}


@pytest.mark.parametrize(
    "exception, expected_status",
    [
        (PermissionError("Club is not participating"), 403),
        (ValueError("Substitution planning is closed"), 409),
        (ValueError("Outgoing player is not on field"), 409),
    ],
)
def test_endpoint_translates_domain_errors(
    api_dependencies, exception, expected_status
):
    match = MagicMock()
    match.plan_substitution.side_effect = exception
    with patch("app.api.matches.get_match", return_value=match), patch(
        "app.api.matches.club_repository.get_by_user_id",
        return_value=SimpleNamespace(id=5),
    ):
        response = TestClient(app).put(
            "/live_match/12/me/3", json={"new_player": 6}
        )
    assert response.status_code == expected_status
    assert response.json() == {"detail": str(exception)}


def test_endpoint_requires_authentication():
    old_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    try:
        response = TestClient(app).put(
            "/live_match/12/me/3", json={"new_player": 6}
        )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)
    assert response.status_code == 401


@pytest.mark.parametrize("body", [{}, {"new_player": "invalid"}, {"new_player": None}])
def test_endpoint_invalid_body_returns_422(api_dependencies, body):
    response = TestClient(app).put("/live_match/12/me/3", json=body)
    assert response.status_code == 422
