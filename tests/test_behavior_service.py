import pytest
from unittest.mock import MagicMock, patch

from app.services.behavior_service import get_behavior


@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_get_behavior_success(mock_get_club, mock_get_behavior):
    db = MagicMock()

    club = MagicMock()
    club.id = 3
    mock_get_club.return_value = club

    behavior = MagicMock()
    behavior.id = 7
    mock_get_behavior.return_value = behavior

    result = get_behavior(
        db=db,
        user_id=1,
        behavior_id=7,
    )

    assert result == behavior

    mock_get_club.assert_called_once_with(db, 1)
    mock_get_behavior.assert_called_once_with(
        db=db,
        club_id=3,
        behavior_id=7,
    )


@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_get_behavior_not_found(mock_get_club, mock_get_behavior):
    db = MagicMock()

    club = MagicMock()
    club.id = 3
    mock_get_club.return_value = club

    mock_get_behavior.return_value = None

    with pytest.raises(LookupError, match="Behavior not found"):
        get_behavior(
            db=db,
            user_id=1,
            behavior_id=999,
        )

    mock_get_behavior.assert_called_once_with(
        db=db,
        club_id=3,
        behavior_id=999,
    )


@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_get_behavior_user_without_club(
    mock_get_club,
    mock_get_behavior,
):
    db = MagicMock()

    mock_get_club.return_value = None

    with pytest.raises(ValueError, match="User does not have a club"):
        get_behavior(
            db=db,
            user_id=1,
            behavior_id=7,
        )

    mock_get_behavior.assert_not_called()
