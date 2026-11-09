from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.game.models.match import MatchState
from app.game.penalties import PenaltySide
from app.services import match_service


@pytest.fixture
def choice_case(monkeypatch):
    session = Mock()
    match = SimpleNamespace(
        state=MatchState.IN_PROGRESS,
        participation_a=SimpleNamespace(club_id=10),
        participation_b=SimpleNamespace(club_id=20),
        penalty_session=session,
    )
    get_match = Mock(return_value=match)
    get_club = Mock(return_value=SimpleNamespace(id=10))

    monkeypatch.setattr(match_service, "get_match", get_match)
    monkeypatch.setattr(
        match_service.club_repository,
        "get_by_user_id",
        get_club,
    )

    return SimpleNamespace(
        db=Mock(),
        match=match,
        session=session,
        get_match=get_match,
        get_club=get_club,
    )


@pytest.mark.parametrize("club_id", [10, 20])
def test_participating_club_can_submit_choice(choice_case, club_id):
    case = choice_case
    case.get_club.return_value = SimpleNamespace(id=club_id)

    match_service.submit_penalty_choice(
        db=case.db,
        user_id=1,
        match_id=100,
        turn=1,
        side=PenaltySide.LEFT,
    )

    case.get_match.assert_called_once_with(100)
    case.get_club.assert_called_once_with(case.db, 1)
    case.session.submit_choice.assert_called_once_with(
        club_id=club_id,
        turn=1,
        side=PenaltySide.LEFT,
    )


def test_missing_match_rejects_choice(choice_case):
    case = choice_case
    case.get_match.return_value = None

    with pytest.raises(LookupError, match="Match not found"):
        match_service.submit_penalty_choice(
            case.db, 1, 100, 1, PenaltySide.LEFT,
        )

    case.get_club.assert_not_called()
    case.session.submit_choice.assert_not_called()


@pytest.mark.parametrize(
    "club, message",
    [
        (None, "User has no club"),
        (
            SimpleNamespace(id=30),
            "User is not participating in this match",
        ),
    ],
)
def test_unauthorized_club_cannot_submit(
    choice_case,
    club,
    message,
):
    case = choice_case
    case.get_club.return_value = club

    with pytest.raises(PermissionError, match=message):
        match_service.submit_penalty_choice(
            case.db, 1, 100, 1, PenaltySide.LEFT,
        )

    case.session.submit_choice.assert_not_called()


@pytest.mark.parametrize(
    "state",
    [MatchState.NOT_STARTED, MatchState.FINISHED],
)
def test_match_must_be_in_progress(choice_case, state):
    case = choice_case
    case.match.state = state

    with pytest.raises(ValueError, match="Match is not in progress"):
        match_service.submit_penalty_choice(
            case.db, 1, 100, 1, PenaltySide.LEFT,
        )

    case.session.submit_choice.assert_not_called()


def test_match_requires_penalty_session(choice_case):
    case = choice_case
    case.match.penalty_session = None

    with pytest.raises(ValueError, match="no active penalty shootout"):
        match_service.submit_penalty_choice(
            case.db, 1, 100, 1, PenaltySide.LEFT,
        )

    case.session.submit_choice.assert_not_called()


def test_session_validation_error_is_propagated(choice_case):
    case = choice_case
    case.session.submit_choice.side_effect = ValueError(
        "Penalty turn deadline has passed",
    )

    with pytest.raises(ValueError, match="deadline has passed"):
        match_service.submit_penalty_choice(
            case.db, 1, 100, 1, PenaltySide.LEFT,
        )

    case.session.submit_choice.assert_called_once()
