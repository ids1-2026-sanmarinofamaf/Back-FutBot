import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import IntegrityError

from app.schemas.behavior import BehaviorIn
from app.services.behavior_service import (
    ActiveCompetitionError,
    BehaviorValidationError,
    DefaultBehaviorModificationError,
    create_behavior,
    delete_behavior,
    get_behavior,
    update_behavior,
    validate_behavior,
)


VALID_CODE = "def play():\n    return wait()\n"
UPDATED_CODE = "def play():\n    _, pos = self()\n    return wait()\n"
INVALID_CODE = "def play():\n    return waiit()\n"


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


def test_validate_behavior_success():
    assert validate_behavior(VALID_CODE) is True


def test_validate_behavior_invalid_raises_validation_error():
    with pytest.raises(BehaviorValidationError):
        validate_behavior(INVALID_CODE)


# Tests for create_behavior

@patch("app.services.behavior_service.behavior_repository.save")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_create_behavior_success(mock_get_club, mock_save):
    db = MagicMock()

    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    data = BehaviorIn(name="  Presión Alta  ", code=VALID_CODE)

    result = create_behavior(db=db, user_id=1, data=data)

    assert result.club_id == 5
    assert result.name == "Presión Alta"
    assert result.code == VALID_CODE
    assert result.is_default is False

    mock_get_club.assert_called_once_with(db, 1)
    mock_save.assert_called_once_with(db, result)
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


@patch("app.services.behavior_service.behavior_repository.save")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_create_behavior_user_without_club(mock_get_club, mock_save):
    db = MagicMock()
    mock_get_club.return_value = None

    data = BehaviorIn(name="Delantero", code=VALID_CODE)

    with pytest.raises(ValueError, match="User does not have a club"):
        create_behavior(db=db, user_id=1, data=data)

    mock_save.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@pytest.mark.parametrize("empty_name", ["", "   "])
@patch("app.services.behavior_service.behavior_repository.save")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_create_behavior_invalid_name_empty_or_whitespace(
    mock_get_club, mock_save, empty_name
):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    data = BehaviorIn(name=empty_name, code=VALID_CODE)

    with pytest.raises(ValueError, match="Behavior name cannot be empty"):
        create_behavior(db=db, user_id=1, data=data)

    mock_save.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@pytest.mark.parametrize("short_name", ["a", "ab", "  ab  "])
@patch("app.services.behavior_service.behavior_repository.save")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_create_behavior_invalid_name_too_short(
    mock_get_club, mock_save, short_name
):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    data = BehaviorIn(name=short_name, code=VALID_CODE)

    with pytest.raises(
        ValueError, match="Behavior name must be at least 3 characters long"
    ):
        create_behavior(db=db, user_id=1, data=data)

    mock_save.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.behavior_service.behavior_repository.save")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_create_behavior_invalid_name_too_long(mock_get_club, mock_save):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    data = BehaviorIn(name="a" * 256, code=VALID_CODE)

    with pytest.raises(
        ValueError, match="Behavior name cannot exceed 255 characters"
    ):
        create_behavior(db=db, user_id=1, data=data)

    mock_save.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.behavior_service.behavior_repository.save")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_create_behavior_invalid_code_rolls_back(mock_get_club, mock_save):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    data = BehaviorIn(name="Delantero", code=INVALID_CODE)

    with pytest.raises(BehaviorValidationError):
        create_behavior(db=db, user_id=1, data=data)

    mock_save.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


# Tests for update_behavior

@patch("app.services.behavior_service.behavior_repository.save")
@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_update_behavior_success(
    mock_get_club, mock_get_behavior, mock_save
):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    behavior = MagicMock()
    behavior.id = 10
    behavior.club_id = 5
    behavior.name = "Viejo Nombre"
    behavior.code = VALID_CODE
    behavior.is_default = False
    mock_get_behavior.return_value = behavior

    data = BehaviorIn(name="  Nuevo Nombre  ", code=UPDATED_CODE)

    result = update_behavior(
        db=db,
        user_id=1,
        behavior_id=10,
        data=data,
    )

    assert result == behavior
    assert behavior.name == "Nuevo Nombre"
    assert behavior.code == UPDATED_CODE

    mock_get_behavior.assert_called_once_with(
        db=db,
        club_id=5,
        behavior_id=10,
    )
    mock_save.assert_called_once_with(db, behavior)
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


@patch("app.services.behavior_service.behavior_repository.save")
@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_update_behavior_user_without_club(
    mock_get_club, mock_get_behavior, mock_save
):
    db = MagicMock()
    mock_get_club.return_value = None

    data = BehaviorIn(name="Nuevo Nombre", code=VALID_CODE)

    with pytest.raises(ValueError, match="User does not have a club"):
        update_behavior(db=db, user_id=1, behavior_id=10, data=data)

    mock_get_behavior.assert_not_called()
    mock_save.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.behavior_service.behavior_repository.save")
@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_update_behavior_not_found_or_other_club(
    mock_get_club, mock_get_behavior, mock_save
):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club
    mock_get_behavior.return_value = None

    data = BehaviorIn(name="Nuevo Nombre", code=VALID_CODE)

    with pytest.raises(LookupError, match="Behavior not found"):
        update_behavior(db=db, user_id=1, behavior_id=999, data=data)

    mock_save.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.behavior_service.behavior_repository.save")
@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_update_behavior_default_raises_error(
    mock_get_club, mock_get_behavior, mock_save
):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    default_behavior = MagicMock()
    default_behavior.id = 1
    default_behavior.is_default = True
    mock_get_behavior.return_value = default_behavior

    data = BehaviorIn(name="Nuevo Nombre", code=VALID_CODE)

    with pytest.raises(
        DefaultBehaviorModificationError,
        match="Default behaviors cannot be modified",
    ):
        update_behavior(db=db, user_id=1, behavior_id=1, data=data)

    mock_save.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@pytest.mark.parametrize(
    "invalid_name,expected_msg",
    [
        ("", "Behavior name cannot be empty"),
        ("ab", "Behavior name must be at least 3 characters long"),
        ("a" * 256, "Behavior name cannot exceed 255 characters"),
    ],
)
@patch("app.services.behavior_service.behavior_repository.save")
@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_update_behavior_invalid_name_rolls_back(
    mock_get_club,
    mock_get_behavior,
    mock_save,
    invalid_name,
    expected_msg,
):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    behavior = MagicMock()
    behavior.id = 10
    behavior.is_default = False
    mock_get_behavior.return_value = behavior

    data = BehaviorIn(name=invalid_name, code=VALID_CODE)

    with pytest.raises(ValueError, match=expected_msg):
        update_behavior(db=db, user_id=1, behavior_id=10, data=data)

    mock_save.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.behavior_service.behavior_repository.save")
@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_update_behavior_invalid_code_rolls_back(
    mock_get_club, mock_get_behavior, mock_save
):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    behavior = MagicMock()
    behavior.id = 10
    behavior.is_default = False
    mock_get_behavior.return_value = behavior

    data = BehaviorIn(name="Nuevo Nombre", code=INVALID_CODE)

    with pytest.raises(BehaviorValidationError):
        update_behavior(db=db, user_id=1, behavior_id=10, data=data)

    mock_save.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.behavior_service.behavior_repository.save")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_create_behavior_duplicate_name_integrity_error_rolls_back(
    mock_get_club, mock_save
):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club
    mock_save.side_effect = IntegrityError("INSERT", {}, Exception("uq_behavior_club_name"))

    data = BehaviorIn(name="Presión Alta", code=VALID_CODE)

    with pytest.raises(ValueError, match="Behavior name already exists"):
        create_behavior(db=db, user_id=1, data=data)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.behavior_service.behavior_repository.save")
@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_update_behavior_duplicate_name_integrity_error_rolls_back(
    mock_get_club, mock_get_behavior, mock_save
):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    behavior = MagicMock()
    behavior.id = 10
    behavior.is_default = False
    mock_get_behavior.return_value = behavior
    mock_save.side_effect = IntegrityError("UPDATE", {}, Exception("uq_behavior_club_name"))

    data = BehaviorIn(name="Nombre Repetido", code=UPDATED_CODE)

    with pytest.raises(ValueError, match="Behavior name already exists"):
        update_behavior(db=db, user_id=1, behavior_id=10, data=data)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.behavior_service.behavior_repository.delete")
@patch("app.services.behavior_service._unassign_behavior_from_rosters")
@patch("app.services.behavior_service._has_active_friendly_game", return_value=False)
@patch("app.services.behavior_service._has_active_league", return_value=False)
@patch("app.services.behavior_service.is_club_in_active_match", return_value=False)
@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_delete_behavior_success(
    mock_get_club,
    mock_get_behavior,
    mock_active_match,
    mock_active_league,
    mock_active_friendly,
    mock_unassign,
    mock_delete,
):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    behavior = MagicMock()
    behavior.id = 10
    behavior.is_default = False
    mock_get_behavior.return_value = behavior

    delete_behavior(db=db, user_id=1, behavior_id=10)

    mock_get_club.assert_called_once_with(db, 1)
    mock_get_behavior.assert_called_once_with(db=db, club_id=5, behavior_id=10)
    mock_active_match.assert_called_once_with(5)
    mock_active_league.assert_called_once_with(db, 5)
    mock_active_friendly.assert_called_once_with(db, 5)
    mock_unassign.assert_called_once_with(db, 10)
    mock_delete.assert_called_once_with(db, behavior)
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_delete_behavior_user_without_club(mock_get_club):
    db = MagicMock()
    mock_get_club.return_value = None

    with pytest.raises(ValueError, match="User does not have a club"):
        delete_behavior(db=db, user_id=1, behavior_id=10)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_delete_behavior_not_found(mock_get_club, mock_get_behavior):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club
    mock_get_behavior.return_value = None

    with pytest.raises(LookupError, match="Behavior not found"):
        delete_behavior(db=db, user_id=1, behavior_id=999)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_delete_behavior_default_raises_error(mock_get_club, mock_get_behavior):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    behavior = MagicMock()
    behavior.id = 1
    behavior.is_default = True
    mock_get_behavior.return_value = behavior

    with pytest.raises(DefaultBehaviorModificationError, match="Default behaviors cannot be modified"):
        delete_behavior(db=db, user_id=1, behavior_id=1)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.behavior_service.is_club_in_active_match", return_value=True)
@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_delete_behavior_active_match_raises_error(
    mock_get_club,
    mock_get_behavior,
    mock_active_match,
):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    behavior = MagicMock()
    behavior.id = 10
    behavior.is_default = False
    mock_get_behavior.return_value = behavior

    with pytest.raises(
        ActiveCompetitionError,
        match="No se puede realizar esta acción mientras se participe en un partido o competencia activa.",
    ):
        delete_behavior(db=db, user_id=1, behavior_id=10)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.behavior_service._has_active_league", return_value=True)
@patch("app.services.behavior_service.is_club_in_active_match", return_value=False)
@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_delete_behavior_active_league_raises_error(
    mock_get_club,
    mock_get_behavior,
    mock_active_match,
    mock_active_league,
):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    behavior = MagicMock()
    behavior.id = 10
    behavior.is_default = False
    mock_get_behavior.return_value = behavior

    with pytest.raises(
        ActiveCompetitionError,
        match="No se puede realizar esta acción mientras se participe en un partido o competencia activa.",
    ):
        delete_behavior(db=db, user_id=1, behavior_id=10)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.behavior_service._has_active_friendly_game", return_value=True)
@patch("app.services.behavior_service._has_active_league", return_value=False)
@patch("app.services.behavior_service.is_club_in_active_match", return_value=False)
@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_delete_behavior_active_friendly_game_raises_error(
    mock_get_club,
    mock_get_behavior,
    mock_active_match,
    mock_active_league,
    mock_active_friendly,
):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    behavior = MagicMock()
    behavior.id = 10
    behavior.is_default = False
    mock_get_behavior.return_value = behavior

    with pytest.raises(
        ActiveCompetitionError,
        match="No se puede realizar esta acción mientras se participe en un partido o competencia activa.",
    ):
        delete_behavior(db=db, user_id=1, behavior_id=10)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@patch("app.services.behavior_service.behavior_repository.delete")
@patch("app.services.behavior_service._unassign_behavior_from_rosters")
@patch("app.services.behavior_service._has_active_friendly_game", return_value=False)
@patch("app.services.behavior_service._has_active_league", return_value=False)
@patch("app.services.behavior_service.is_club_in_active_match", return_value=False)
@patch("app.services.behavior_service.behavior_repository.get_available_by_id")
@patch("app.services.behavior_service.club_repository.get_by_user_id")
def test_delete_behavior_exception_rolls_back(
    mock_get_club,
    mock_get_behavior,
    mock_active_match,
    mock_active_league,
    mock_active_friendly,
    mock_unassign,
    mock_delete,
):
    db = MagicMock()
    club = MagicMock()
    club.id = 5
    mock_get_club.return_value = club

    behavior = MagicMock()
    behavior.id = 10
    behavior.is_default = False
    mock_get_behavior.return_value = behavior

    mock_delete.side_effect = Exception("DB error")

    with pytest.raises(Exception, match="DB error"):
        delete_behavior(db=db, user_id=1, behavior_id=10)

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_has_active_league():
    from app.services.behavior_service import _has_active_league
    db = MagicMock()
    db.scalar.return_value = 1
    assert _has_active_league(db, 5) is True
    db.scalar.return_value = None
    assert _has_active_league(db, 5) is False


def test_has_active_friendly_game():
    from app.services.behavior_service import _has_active_friendly_game
    db = MagicMock()
    db.scalar.return_value = 1
    assert _has_active_friendly_game(db, 5) is True
    db.scalar.return_value = None
    assert _has_active_friendly_game(db, 5) is False


def test_unassign_behavior_from_rosters():
    from app.services.behavior_service import _unassign_behavior_from_rosters
    db = MagicMock()
    _unassign_behavior_from_rosters(db, 10)
    db.execute.assert_called_once()



