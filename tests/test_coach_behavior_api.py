from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.database import SessionLocal
from app.game.active_matches import active_matches
from app.main import app
from app.models.club import Club
from app.models.coach_behavior import CoachBehavior
from app.models.roster import Formation, Roster
from app.models.user import User


client = TestClient(app)

EMAIL = "coach-behaviors@mail.com"
PASSWORD = "secreta123"
OTHER_EMAIL = "other-coach-behaviors@mail.com"

URL = "/clubes/me/coach_behaviors"
CODE = "def coach():\n    return []\n"

MSG_LIVE_MATCH = "User cannot perform this action while playing a live match."


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
        club=Club(name="coach-behaviors-club"),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    yield user

    db.query(CoachBehavior).delete()
    db.query(Club).delete()
    db.query(User).delete()
    db.commit()


@pytest.fixture
def other_club(db, user):
    other_user = User(
        email=OTHER_EMAIL,
        hash_passwd=get_password_hash(PASSWORD),
        club=Club(name="other-coach-club"),
    )
    db.add(other_user)
    db.commit()

    return other_user.club


@pytest.fixture
def club_in_active_match(user):
    match = MagicMock()
    match.participation_a.club_id = user.club.id
    match.participation_b.club_id = -1
    active_matches[999] = match

    yield

    active_matches.pop(999, None)


def login(email=EMAIL):
    response = client.post(
        "/sessions",
        json={
            "email": email,
            "password": PASSWORD,
        },
    )

    return response.json()["token"]


def auth_header(token=None):
    return {
        "Authorization": f"Bearer {token or login()}"
    }


def create(name="Offensive", code=CODE):
    return client.post(URL, json={"name": name, "code": code}, headers=auth_header())


# Tests for POST /clubes/me/coach_behaviors

def test_create_without_token_returns_401():
    response = client.post(URL, json={"name": "Offensive", "code": CODE})

    assert response.status_code == 401


def test_create_returns_201_and_persists(user, db):
    response = create()

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Offensive"
    assert body["code"] == CODE

    saved = db.get(CoachBehavior, body["coach_behavior_id"])
    assert saved.club_id == user.club.id
    assert saved.code == CODE


@pytest.mark.parametrize("body", [{"name": "Offensive"}, {"code": CODE}, {"name": "", "code": CODE}])
def test_create_with_missing_data_returns_400(user, body):
    response = client.post(URL, json=body, headers=auth_header())

    assert response.status_code == 400


@pytest.mark.parametrize("code, message", [
    ("def play():\n    return wait()\n", "Se debe definir la función principal 'def coach():'"),
    ("coach = 3\n", "Se debe definir la función principal 'def coach():'"),
    ("def coach(:\n", "Error sintáctico"),
])
def test_create_without_callable_coach_returns_400(user, code, message):
    response = create(code=code)

    assert response.status_code == 400
    assert message in response.json()["detail"]


@pytest.mark.parametrize("code, message", [
    ("import os\ndef coach():\n    return []\n", "No se permiten importaciones"),
    ("from os import system\ndef coach():\n    return []\n", "No se permiten importaciones"),
    ("def coach():\n    open('x')\n    return []\n", "No se permite el uso de 'open'"),
    ("def coach():\n    return ().__class__.__bases__\n", "No se permite el acceso interno"),
    ("while True:\n    pass\ndef coach():\n    return []\n", "En el nivel principal del archivo"),
    ("print('x')\ndef coach():\n    return []\n", "En el nivel principal del archivo"),
    ("x = len([])\ndef coach():\n    return []\n", "No se permiten llamadas a funciones fuera de def coach()"),
])
def test_create_with_forbidden_code_returns_400(user, code, message):
    response = create(code=code)

    assert response.status_code == 400
    assert message in response.json()["detail"]


@pytest.mark.parametrize("code, message", [
    ("def coach():\n    pass\n", "debe retornar una lista"),
    ("def coach(x):\n    return []\n", "no debe llevar argumentos"),
    ("def coach():\n    return [move((1.0, 0.0), 1.0)]\n", "'move'"),
    ("def coach():\n    return 3\n", "debe retornar una lista"),
    ("def coach():\n    return [1]\n", "assign(...) o substitute(...)"),
    ("def coach():\n    return [1 / 0]\n", "Error de ejecución en coach()"),
    ("def coach():\n    while True:\n        pass\n    return []\n", "tiempo máximo"),
])
def test_create_with_code_that_fails_in_a_match_returns_400(user, db, code, message):
    response = create(code=code)

    assert response.status_code == 400
    assert message in response.json()["detail"]
    assert db.query(CoachBehavior).count() == 0


def test_create_with_assign_and_substitute_returns_201(user):
    code = (
        "def coach():\n"
        "    if trigger() == CoachTrigger.GOAL_AGAINST and can_substitute():\n"
        "        return [substitute(1, bench()[0]), assign(2, available_behaviors()[0])]\n"
        "    return [assign(1, 'Attacker')]\n"
    )

    response = create(code=code)

    assert response.status_code == 201


def test_create_with_default_behavior_name_returns_409(user):
    response = create(name="Attacker")

    assert response.status_code == 409
    assert response.json()["detail"] == "Coach behavior name matches a default behavior."


def test_create_with_duplicated_name_returns_409(user):
    create()
    response = create()

    assert response.status_code == 409
    assert response.json()["detail"] == "Coach behavior name already exists."


def test_create_same_name_as_other_club_is_allowed(user, other_club, db):
    db.add(CoachBehavior(club_id=other_club.id, name="Offensive", code=CODE))
    db.commit()

    response = create()

    assert response.status_code == 201


def test_create_during_active_match_returns_403(user, club_in_active_match, db):
    response = create()

    assert response.status_code == 403
    assert response.json()["detail"] == MSG_LIVE_MATCH
    assert db.query(CoachBehavior).count() == 0


# Tests for GET /clubes/me/coach_behaviors

def test_list_without_token_returns_401():
    response = client.get(URL)

    assert response.status_code == 401


def test_list_without_coach_behaviors_returns_empty_list(user):
    response = client.get(URL, headers=auth_header())

    assert response.status_code == 200
    assert response.json() == []


def test_list_returns_only_own_coach_behaviors(user, other_club, db):
    own = CoachBehavior(club_id=user.club.id, name="Mio", code=CODE)
    foreign = CoachBehavior(club_id=other_club.id, name="Ajeno", code=CODE)
    db.add_all([own, foreign])
    db.commit()

    response = client.get(URL, headers=auth_header())

    assert response.status_code == 200
    assert response.json() == [{"coach_behavior_id": own.id, "name": "Mio", "code": CODE}]


# Tests for GET /clubes/me/coach_behaviors/{coach_behavior_id}

def test_get_by_id_without_token_returns_401():
    response = client.get(f"{URL}/1")

    assert response.status_code == 401


def test_get_by_id_returns_coach_behavior_with_code(user, db):
    coach_behavior = CoachBehavior(club_id=user.club.id, name="Mio", code=CODE)
    db.add(coach_behavior)
    db.commit()

    response = client.get(f"{URL}/{coach_behavior.id}", headers=auth_header())

    assert response.status_code == 200
    assert response.json() == {"coach_behavior_id": coach_behavior.id, "name": "Mio", "code": CODE}


def test_get_by_id_nonexistent_returns_404(user):
    response = client.get(f"{URL}/999999", headers=auth_header())

    assert response.status_code == 404
    assert response.json()["detail"] == "Coach behavior not found."


def test_get_by_id_other_club_coach_behavior_returns_404(user, other_club, db):
    foreign = CoachBehavior(club_id=other_club.id, name="Ajeno", code=CODE)
    db.add(foreign)
    db.commit()

    response = client.get(f"{URL}/{foreign.id}", headers=auth_header())

    assert response.status_code == 404
    assert response.json()["detail"] == "Coach behavior not found."


def test_get_by_id_user_without_club_returns_404(user, db):
    db.add(User(email=OTHER_EMAIL, hash_passwd=get_password_hash(PASSWORD)))
    db.commit()

    response = client.get(f"{URL}/1", headers=auth_header(login(OTHER_EMAIL)))

    assert response.status_code == 404
    assert response.json()["detail"] == "User does not have a club"


# Tests for DELETE /clubes/me/coach_behaviors/{coach_behavior_id}

def test_delete_without_token_returns_401():
    response = client.delete(f"{URL}/1")

    assert response.status_code == 401


def test_delete_returns_204_and_removes(user, db):
    coach_behavior_id = create().json()["coach_behavior_id"]

    response = client.delete(f"{URL}/{coach_behavior_id}", headers=auth_header())

    assert response.status_code == 204
    db.expire_all()
    assert db.get(CoachBehavior, coach_behavior_id) is None


def test_delete_nonexistent_returns_404(user):
    response = client.delete(f"{URL}/999999", headers=auth_header())

    assert response.status_code == 404
    assert response.json()["detail"] == "Coach behavior not found."


def test_delete_other_club_coach_behavior_returns_404(user, other_club, db):
    foreign = CoachBehavior(club_id=other_club.id, name="Ajeno", code=CODE)
    db.add(foreign)
    db.commit()

    response = client.delete(f"{URL}/{foreign.id}", headers=auth_header())

    assert response.status_code == 404
    db.expire_all()
    assert db.get(CoachBehavior, foreign.id) is not None


def test_delete_during_active_match_returns_403(user, db, club_in_active_match):
    coach_behavior = CoachBehavior(club_id=user.club.id, name="Mio", code=CODE)
    db.add(coach_behavior)
    db.commit()

    response = client.delete(f"{URL}/{coach_behavior.id}", headers=auth_header())

    assert response.status_code == 403
    assert response.json()["detail"] == MSG_LIVE_MATCH
    db.expire_all()
    assert db.get(CoachBehavior, coach_behavior.id) is not None


def test_delete_coach_behavior_assigned_to_roster_unassigns_it(user, db):
    coach_behavior = CoachBehavior(club_id=user.club.id, name="Mio", code=CODE)
    db.add(coach_behavior)
    db.commit()

    roster = Roster(
        club_id=user.club.id,
        formation=Formation.DEFENSIVE,
        coach_behavior_id=coach_behavior.id,
    )
    db.add(roster)
    db.commit()

    response = client.delete(f"{URL}/{coach_behavior.id}", headers=auth_header())

    assert response.status_code == 204
    db.expire_all()
    assert db.get(Roster, roster.id).coach_behavior_id is None

    db.delete(roster)
    db.commit()
