from unittest.mock import MagicMock

import pytest

from app.game.active_matches import active_matches, is_club_in_active_match


def make_match(match_id, club_a_id, club_b_id):
    match = MagicMock()
    match.match_id = match_id
    match.participation_a.club_id = club_a_id
    match.participation_b.club_id = club_b_id
    return match


@pytest.fixture(autouse=True)
def clear_active_matches():
    active_matches.clear()
    yield
    active_matches.clear()


def test_no_active_matches_returns_false():
    assert is_club_in_active_match(1) is False


def test_club_in_participation_a_returns_true():
    active_matches[10] = make_match(10, club_a_id=1, club_b_id=2)

    assert is_club_in_active_match(1) is True


def test_club_in_participation_b_returns_true():
    active_matches[10] = make_match(10, club_a_id=1, club_b_id=2)

    assert is_club_in_active_match(2) is True


def test_club_not_in_any_active_match_returns_false():
    active_matches[10] = make_match(10, club_a_id=1, club_b_id=2)
    active_matches[11] = make_match(11, club_a_id=3, club_b_id=4)

    assert is_club_in_active_match(5) is False


def test_club_in_a_later_match_returns_true():
    active_matches[10] = make_match(10, club_a_id=1, club_b_id=2)
    active_matches[11] = make_match(11, club_a_id=3, club_b_id=4)

    assert is_club_in_active_match(4) is True
