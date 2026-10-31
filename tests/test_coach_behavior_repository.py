import pytest

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import engine
from app.models.user import User
from app.models.club import Club
from app.models.coach_behavior import CoachBehavior
from app.repositories import coach_behavior_repository


COACH_CODE = "def coach():\n    return []\n"


@pytest.fixture
def db():
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN")
        transaction = connection.get_transaction()

        with Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

        transaction.rollback()


@pytest.fixture
def clubs(db):
    clubs = []

    for i in range(2):
        user = User(
            email=f"coach_behavior_repository_user_{i}@example.com",
            hash_passwd="test_hash",
        )
        db.add(user)
        db.flush()

        club = Club(
            user_id=user.id,
            name=f"Coach Behavior Repository Club {i}",
        )
        db.add(club)
        db.flush()

        clubs.append(club)

    return clubs


def create_coach_behavior(db, club, name):
    coach_behavior = CoachBehavior(club_id=club.id, name=name, code=COACH_CODE)
    coach_behavior_repository.save(db, coach_behavior)
    return coach_behavior


def test_save_assigns_id(db, clubs):
    coach_behavior = create_coach_behavior(db, clubs[0], "Offensive")

    assert coach_behavior.id is not None


def test_save_duplicated_name_in_same_club_raises_integrity_error(db, clubs):
    create_coach_behavior(db, clubs[0], "Offensive")

    with pytest.raises(IntegrityError):
        create_coach_behavior(db, clubs[0], "Offensive")


def test_save_same_name_in_different_clubs_is_allowed(db, clubs):
    first = create_coach_behavior(db, clubs[0], "Offensive")
    second = create_coach_behavior(db, clubs[1], "Offensive")

    assert first.id != second.id


def test_list_by_club_returns_only_own_coach_behaviors_ordered_by_id(db, clubs):
    first = create_coach_behavior(db, clubs[0], "Offensive")
    second = create_coach_behavior(db, clubs[0], "Defensive")
    create_coach_behavior(db, clubs[1], "Other club")

    result = coach_behavior_repository.list_by_club(db, clubs[0].id)

    assert [cb.id for cb in result] == [first.id, second.id]


def test_list_by_club_without_coach_behaviors_returns_empty_list(db, clubs):
    assert coach_behavior_repository.list_by_club(db, clubs[0].id) == []


def test_get_by_id_for_club_returns_own_coach_behavior(db, clubs):
    coach_behavior = create_coach_behavior(db, clubs[0], "Offensive")

    result = coach_behavior_repository.get_by_id_for_club(
        db, clubs[0].id, coach_behavior.id
    )

    assert result is coach_behavior


def test_get_by_id_for_club_of_other_club_returns_none(db, clubs):
    coach_behavior = create_coach_behavior(db, clubs[1], "Offensive")

    result = coach_behavior_repository.get_by_id_for_club(
        db, clubs[0].id, coach_behavior.id
    )

    assert result is None


def test_get_by_id_for_club_nonexistent_returns_none(db, clubs):
    assert coach_behavior_repository.get_by_id_for_club(db, clubs[0].id, 999999) is None


def test_delete_removes_coach_behavior(db, clubs):
    coach_behavior = create_coach_behavior(db, clubs[0], "Offensive")
    coach_behavior_id = coach_behavior.id

    coach_behavior_repository.delete(db, coach_behavior)

    assert coach_behavior_repository.get_by_id_for_club(
        db, clubs[0].id, coach_behavior_id
    ) is None
