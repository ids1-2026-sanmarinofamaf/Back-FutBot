import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.database import SessionLocal
from app.main import app
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.user import User


client = TestClient(app)

EMAIL = "behaviors@mail.com"
PASSWORD = "secreta123"
OTHER_EMAIL = "other-behaviors@mail.com"
NO_CLUB_EMAIL = "no-club-behaviors@mail.com"

CODE = "def play(ctx):\n    return wait()\n"


@pytest.fixture
def db():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def user(db):
    user = User(
        email=EMAIL,
        hash_passwd=get_password_hash(PASSWORD),
        club=Club(name="behaviors-club"),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    yield user

    # default behaviors are seeded by the migrations, keep them
    db.query(Behavior).filter(Behavior.is_default.is_(False)).delete()
    db.query(Club).delete()
    db.query(User).delete()
    db.commit()


@pytest.fixture
def other_club(db, user):
    other_user = User(
        email=OTHER_EMAIL,
        hash_passwd=get_password_hash(PASSWORD),
        club=Club(name="other-club"),
    )
    db.add(other_user)
    db.commit()

    return other_user.club


def login(email=EMAIL):
    response = client.post(
        "/sessions",
        json={
            "email": email,
            "password": PASSWORD,
        },
    )

    return response.json()["token"]


def auth_header(token):
    return {
        "Authorization": f"Bearer {token}"
    }


def default_behavior_ids(db):
    return {
        behavior.id
        for behavior in db.query(Behavior).filter(Behavior.is_default.is_(True))
    }


def test_get_behaviors_without_token_returns_401():
    response = client.get("/clubes/me/behaviors")

    assert response.status_code == 401


def test_get_behaviors_with_invalid_token_returns_401():
    response = client.get(
        "/clubes/me/behaviors",
        headers=auth_header("invalid.token.value"),
    )

    assert response.status_code == 401


def test_get_behaviors_returns_club_behaviors_and_defaults(user, db):
    own = Behavior(club_id=user.club.id, name="Delantero", code=CODE)
    db.add(own)
    db.commit()

    response = client.get(
        "/clubes/me/behaviors",
        headers=auth_header(login()),
    )

    assert response.status_code == 200
    body = response.json()

    returned_ids = {behavior["behavior_id"] for behavior in body}
    assert returned_ids == default_behavior_ids(db) | {own.id}

    own_out = next(b for b in body if b["behavior_id"] == own.id)
    assert own_out == {"behavior_id": own.id, "name": "Delantero", "code": CODE}


def test_get_behaviors_does_not_return_other_clubs_behaviors(user, other_club, db):
    own = Behavior(club_id=user.club.id, name="Mio", code=CODE)
    foreign = Behavior(club_id=other_club.id, name="Ajeno", code=CODE)
    db.add_all([own, foreign])
    db.commit()

    response = client.get(
        "/clubes/me/behaviors",
        headers=auth_header(login()),
    )

    assert response.status_code == 200
    returned_ids = {behavior["behavior_id"] for behavior in response.json()}

    assert own.id in returned_ids
    assert foreign.id not in returned_ids


def test_get_behaviors_user_without_club_returns_400(user, db):
    db.add(User(email=NO_CLUB_EMAIL, hash_passwd=get_password_hash(PASSWORD)))
    db.commit()

    response = client.get(
        "/clubes/me/behaviors",
        headers=auth_header(login(NO_CLUB_EMAIL)),
    )

    assert response.status_code == 400
