import pytest

from app.game.match_result import resolve_match_winner


@pytest.mark.parametrize(
    ("club_a", "club_b", "winner_club_id", "expected"),
    [
        ((10, 2), (20, 1), None, 10),
        ((10, 1), (20, 2), None, 20),
        ((10, 2), (20, 1), 10, 10),
        ((10, 1), (20, 2), 20, 20),
        ((10, 1), (20, 1), None, None),
        ((10, 1), (20, 1), 10, 10),
        ((10, 1), (20, 1), 20, 20),
    ],
)
def test_resolve_valid_match_result(
    club_a,
    club_b,
    winner_club_id,
    expected,
):
    assert resolve_match_winner(
        club_a,
        club_b,
        winner_club_id,
    ) == expected


@pytest.mark.parametrize(
    ("club_a", "club_b", "winner_club_id", "message"),
    [
        ((10, 1), (10, 0), None, "cannot play against itself"),
        ((10, -1), (20, 0), None, "cannot be negative"),
        ((10, 0), (20, -1), None, "cannot be negative"),
        ((10, 1), (20, 1), 30, "participating club"),
        ((10, 2), (20, 1), 20, "contradicts"),
        ((10, 1), (20, 2), 10, "contradicts"),
    ],
)
def test_reject_invalid_match_result(
    club_a,
    club_b,
    winner_club_id,
    message,
):
    with pytest.raises(ValueError, match=message):
        resolve_match_winner(club_a, club_b, winner_club_id)
