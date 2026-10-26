
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

CODE = "def play():\n    return wait()\n"
UPDATED_CODE = "def play():\n    _, pos = self()\n    return wait()\n"
INVALID_CODE = "def play():\n    return waiit()\n"


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


# Tests for GET /clubes/me/behaviors

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
    assert own_out == {
        "behavior_id": own.id,
        "name": "Delantero",
        "code": CODE,
        "is_default": False,
    }

    for b in body:
        if b["behavior_id"] != own.id:
            assert b["is_default"] is True


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


# tests for GET /clubes/me/behaviors/{behavior_id}

def test_get_behavior_by_id_returns_own_behavior(user, db):
    behavior = Behavior(
        club_id=user.club.id,
        name="Delantero",
        code=CODE,
    )
    db.add(behavior)
    db.commit()
    db.refresh(behavior)

    response = client.get(
        f"/clubes/me/behaviors/{behavior.id}",
        headers=auth_header(login()),
    )

    assert response.status_code == 200
    assert response.json() == {
        "behavior_id": behavior.id,
        "name": "Delantero",
        "code": CODE,
        "is_default": False,
    }


def test_get_behavior_by_id_returns_default(user, db):
    behavior = (
        db.query(Behavior)
        .filter(Behavior.is_default.is_(True))
        .first()
    )

    assert behavior is not None

    response = client.get(
        f"/clubes/me/behaviors/{behavior.id}",
        headers=auth_header(login()),
    )

    assert response.status_code == 200
    assert response.json() == {
        "behavior_id": behavior.id,
        "name": behavior.name,
        "code": behavior.code,
        "is_default": True,
    }


def test_get_behavior_by_id_other_club_returns_404(
    user, other_club, db
):
    behavior = Behavior(
        club_id=other_club.id,
        name="Ajeno",
        code=CODE,
    )
    db.add(behavior)
    db.commit()
    db.refresh(behavior)

    response = client.get(
        f"/clubes/me/behaviors/{behavior.id}",
        headers=auth_header(login()),
    )

    assert response.status_code == 404


def test_get_behavior_by_id_not_found(user, db):
    max_id = (
        db.query(Behavior.id)
        .order_by(Behavior.id.desc())
        .first()
    )
    nonexistent_id = max_id[0] + 1 if max_id else 1

    response = client.get(
        f"/clubes/me/behaviors/{nonexistent_id}",
        headers=auth_header(login()),
    )

    assert response.status_code == 404


def test_get_behavior_by_id_without_token():
    response = client.get(
        "/clubes/me/behaviors/1"
    )

    assert response.status_code == 401


def test_get_behavior_by_id_invalid_token():
    response = client.get(
        "/clubes/me/behaviors/1",
        headers=auth_header("invalid.token.value"),
    )

    assert response.status_code == 401


def test_get_behavior_by_name_without_token_returns_401():
    response = client.get("/clubes/me/behaviors", params={"name": "Delantero"})

    assert response.status_code == 401


def test_get_behavior_by_name_returns_default_behavior(user, db):
    default = db.query(Behavior).filter(Behavior.is_default.is_(True)).first()

    response = client.get(
        "/clubes/me/behaviors",
        params={"name": default.name},
        headers=auth_header(login()),
    )

    assert response.status_code == 200
    assert response.json() == {"behavior_id": default.id, "code": default.code}


def test_get_behavior_by_name_returns_own_club_behavior(user, db):
    own = Behavior(club_id=user.club.id, name="Mi Delantero", code=CODE)
    db.add(own)
    db.commit()

    response = client.get(
        "/clubes/me/behaviors",
        params={"name": "Mi Delantero"},
        headers=auth_header(login()),
    )

    assert response.status_code == 200
    assert response.json() == {"behavior_id": own.id, "code": CODE}


def test_get_behavior_by_name_not_found_returns_404(user):
    response = client.get(
        "/clubes/me/behaviors",
        params={"name": "No Existe"},
        headers=auth_header(login()),
    )

    assert response.status_code == 404


def test_get_behavior_by_name_from_other_club_returns_404(user, other_club, db):
    db.add(Behavior(club_id=other_club.id, name="Ajeno", code=CODE))
    db.commit()

    response = client.get(
        "/clubes/me/behaviors",
        params={"name": "Ajeno"},
        headers=auth_header(login()),
    )

    assert response.status_code == 404


def test_get_behavior_by_name_user_without_club_returns_400(user, db):
    db.add(User(email=NO_CLUB_EMAIL, hash_passwd=get_password_hash(PASSWORD)))
    db.commit()

    response = client.get(
        "/clubes/me/behaviors",
        params={"name": "Delantero"},
        headers=auth_header(login(NO_CLUB_EMAIL)),
    )

    assert response.status_code == 400


# Tests for POST /clubes/me/behaviors/validate

def test_validate_behavior_without_token_returns_401():
    response = client.post(
        "/clubes/me/behaviors/validate",
        json={"code": "def play():\n    return wait()\n"},
    )

    assert response.status_code == 401


def test_validate_behavior_with_invalid_token_returns_401():
    response = client.post(
        "/clubes/me/behaviors/validate",
        json={"code": "def play():\n    return wait()\n"},
        headers=auth_header("invalid.token.value"),
    )

    assert response.status_code == 401


def test_validate_behavior_valid_code_returns_200(user):
    response = client.post(
        "/clubes/me/behaviors/validate",
        json={"code": "def play():\n    return wait()\n"},
        headers=auth_header(login()),
    )

    assert response.status_code == 200
    assert response.json() == {"valid": True}


def test_validate_behavior_invalid_code_returns_400(user):
    response = client.post(
        "/clubes/me/behaviors/validate",
        json={"code": "def play():\n    return waiit()\n"},
        headers=auth_header(login()),
    )

    assert response.status_code == 400
    assert "waiit" in response.json()["detail"]


# Tests for POST /clubes/me/behaviors

def test_create_behavior_without_token_returns_401():
    response = client.post(
        "/clubes/me/behaviors",
        json={"name": "Presión Alta", "code": CODE},
    )

    assert response.status_code == 401


def test_create_behavior_with_invalid_token_returns_401():
    response = client.post(
        "/clubes/me/behaviors",
        json={"name": "Presión Alta", "code": CODE},
        headers=auth_header("invalid.token.value"),
    )

    assert response.status_code == 401


def test_create_behavior_valid_returns_201_and_persists(user, db):
    response = client.post(
        "/clubes/me/behaviors",
        json={"name": "  Presión Alta  ", "code": CODE},
        headers=auth_header(login()),
    )

    assert response.status_code == 201
    body = response.json()
    assert "behavior_id" in body

    db.expire_all()
    created = db.get(Behavior, body["behavior_id"])
    assert created is not None
    assert created.club_id == user.club.id
    assert created.name == "Presión Alta"
    assert created.code == CODE
    assert created.is_default is False


@pytest.mark.parametrize(
    "invalid_name,expected_detail",
    [
        ("", "Behavior name cannot be empty"),
        ("   ", "Behavior name cannot be empty"),
        ("ab", "Behavior name must be at least 3 characters long"),
        ("a" * 256, "Behavior name cannot exceed 255 characters"),
    ],
)
def test_create_behavior_invalid_name_returns_400(
    user, db, invalid_name, expected_detail
):
    response = client.post(
        "/clubes/me/behaviors",
        json={"name": invalid_name, "code": CODE},
        headers=auth_header(login()),
    )

    assert response.status_code == 400
    assert expected_detail in response.json()["detail"]

    club_behaviors = (
        db.query(Behavior).filter(Behavior.club_id == user.club.id).all()
    )
    assert club_behaviors == []


def test_create_behavior_invalid_code_returns_400(user, db):
    response = client.post(
        "/clubes/me/behaviors",
        json={"name": "Presión Alta", "code": INVALID_CODE},
        headers=auth_header(login()),
    )

    assert response.status_code == 400
    assert "waiit" in response.json()["detail"]

    club_behaviors = (
        db.query(Behavior).filter(Behavior.club_id == user.club.id).all()
    )
    assert club_behaviors == []


def test_create_behavior_user_without_club_returns_400(user, db):
    db.add(User(email=NO_CLUB_EMAIL, hash_passwd=get_password_hash(PASSWORD)))
    db.commit()

    response = client.post(
        "/clubes/me/behaviors",
        json={"name": "Presión Alta", "code": CODE},
        headers=auth_header(login(NO_CLUB_EMAIL)),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "User does not have a club"


# Tests for PUT /clubes/me/behaviors/{behavior_id}

def test_update_behavior_without_token_returns_401():
    response = client.put(
        "/clubes/me/behaviors/1",
        json={"name": "Editado", "code": UPDATED_CODE},
    )

    assert response.status_code == 401


def test_update_behavior_with_invalid_token_returns_401():
    response = client.put(
        "/clubes/me/behaviors/1",
        json={"name": "Editado", "code": UPDATED_CODE},
        headers=auth_header("invalid.token.value"),
    )

    assert response.status_code == 401


def test_update_behavior_own_behavior_returns_204_and_updates_db(user, db):
    behavior = Behavior(
        club_id=user.club.id,
        name="Original",
        code=CODE,
        is_default=False,
    )
    db.add(behavior)
    db.commit()
    db.refresh(behavior)

    response = client.put(
        f"/clubes/me/behaviors/{behavior.id}",
        json={"name": "  Editado  ", "code": UPDATED_CODE},
        headers=auth_header(login()),
    )

    assert response.status_code == 204
    assert response.content == b""

    db.expire_all()
    updated = db.get(Behavior, behavior.id)
    assert updated.name == "Editado"
    assert updated.code == UPDATED_CODE
    assert updated.is_default is False


def test_update_behavior_default_returns_403_and_does_not_modify(user, db):
    default_behavior = (
        db.query(Behavior).filter(Behavior.is_default.is_(True)).first()
    )
    assert default_behavior is not None
    original_name = default_behavior.name
    original_code = default_behavior.code

    response = client.put(
        f"/clubes/me/behaviors/{default_behavior.id}",
        json={"name": "Hackeado", "code": UPDATED_CODE},
        headers=auth_header(login()),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Default behaviors cannot be modified"

    db.expire_all()
    unchanged = db.get(Behavior, default_behavior.id)
    assert unchanged.name == original_name
    assert unchanged.code == original_code


def test_update_behavior_other_club_returns_404(user, other_club, db):
    foreign = Behavior(
        club_id=other_club.id,
        name="Ajeno",
        code=CODE,
        is_default=False,
    )
    db.add(foreign)
    db.commit()
    db.refresh(foreign)

    response = client.put(
        f"/clubes/me/behaviors/{foreign.id}",
        json={"name": "Intentando Editar", "code": UPDATED_CODE},
        headers=auth_header(login()),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Behavior not found"

    db.expire_all()
    unchanged = db.get(Behavior, foreign.id)
    assert unchanged.name == "Ajeno"
    assert unchanged.code == CODE


def test_update_behavior_nonexistent_id_returns_404(user, db):
    max_id = (
        db.query(Behavior.id)
        .order_by(Behavior.id.desc())
        .first()
    )
    nonexistent_id = max_id[0] + 1 if max_id else 1

    response = client.put(
        f"/clubes/me/behaviors/{nonexistent_id}",
        json={"name": "Editado", "code": UPDATED_CODE},
        headers=auth_header(login()),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Behavior not found"


@pytest.mark.parametrize(
    "invalid_name,expected_detail",
    [
        ("", "Behavior name cannot be empty"),
        ("ab", "Behavior name must be at least 3 characters long"),
        ("a" * 256, "Behavior name cannot exceed 255 characters"),
    ],
)
def test_update_behavior_invalid_name_returns_400(
    user, db, invalid_name, expected_detail
):
    behavior = Behavior(
        club_id=user.club.id,
        name="Original",
        code=CODE,
        is_default=False,
    )
    db.add(behavior)
    db.commit()
    db.refresh(behavior)

    response = client.put(
        f"/clubes/me/behaviors/{behavior.id}",
        json={"name": invalid_name, "code": UPDATED_CODE},
        headers=auth_header(login()),
    )

    assert response.status_code == 400
    assert expected_detail in response.json()["detail"]

    db.expire_all()
    unchanged = db.get(Behavior, behavior.id)
    assert unchanged.name == "Original"
    assert unchanged.code == CODE


def test_update_behavior_invalid_code_returns_400(user, db):
    behavior = Behavior(
        club_id=user.club.id,
        name="Original",
        code=CODE,
        is_default=False,
    )
    db.add(behavior)
    db.commit()
    db.refresh(behavior)

    response = client.put(
        f"/clubes/me/behaviors/{behavior.id}",
        json={"name": "Editado", "code": INVALID_CODE},
        headers=auth_header(login()),
    )

    assert response.status_code == 400
    assert "waiit" in response.json()["detail"]

    db.expire_all()
    unchanged = db.get(Behavior, behavior.id)
    assert unchanged.name == "Original"
    assert unchanged.code == CODE


def test_update_behavior_user_without_club_returns_400(user, db):
    db.add(User(email=NO_CLUB_EMAIL, hash_passwd=get_password_hash(PASSWORD)))
    db.commit()

    response = client.put(
        "/clubes/me/behaviors/1",
        json={"name": "Editado", "code": UPDATED_CODE},
        headers=auth_header(login(NO_CLUB_EMAIL)),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "User does not have a club"


