from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.club_service import get_club_by_id, ClubNotFound


def test_get_club_by_id_success():
    db = MagicMock()

    stats = SimpleNamespace(
        total_points=15,
        matches_played=6,
        matches_won=5,
        matches_drawn=0,
        matches_lost=1,
        goals_for=12,
        goals_against=4,
        leagues_played=2,
        leagues_won=1,
    )

    club = SimpleNamespace(
        id=25,
        name="River",
        avatar="default",
        statistics=stats,
    )

    with patch(
        "app.services.club_service.club_repository.get_by_id",
        return_value=club,
    ) as mock_get:
        result = get_club_by_id(db, 25)

    mock_get.assert_called_once_with(db, 25)

    assert result.club_name == "River"
    assert result.club_avatar == "default"
    assert result.statistics.total_points == 15
    assert result.statistics.matches_won == 5
    assert result.statistics.goals_for == 12


def test_get_club_by_id_not_found():
    db = MagicMock()

    with patch(
        "app.services.club_service.club_repository.get_by_id",
        return_value=None,
    ) as mock_get:

        with pytest.raises(ClubNotFound):
            get_club_by_id(db, 999)

    mock_get.assert_called_once_with(db, 999)