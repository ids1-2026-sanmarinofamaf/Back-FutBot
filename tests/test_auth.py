from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.security import ALGORITHM, SECRET_KEY, create_access_token, get_password_hash
from app.database import SessionLocal
from app.main import app
from app.models.club import Club
from app.models.user import User

EMAIL = "juan@mail.com"
PASSWORD = "secreta123"

client = TestClient(app)


@pytest.fixture
def user():
    db = SessionLocal()
    user = User(email=EMAIL, hash_passwd=get_password_hash(PASSWORD), club=Club(name="juan"))
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(Club).delete()
    db.query(User).delete()
    db.commit()
    db.close()


def login(email=EMAIL, password=PASSWORD):
    return client.post("/sessions", json={"email": email, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_login_ok_returns_token(user):
    response = login()
    assert response.status_code == 200
    assert "token" in response.json()


def test_token_has_email_exp_and_jti(user):
    token = login().json()["token"]
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == EMAIL
    assert "exp" in payload
    assert "jti" in payload


def test_two_logins_give_different_jti(user):
    first = jwt.decode(login().json()["token"], SECRET_KEY, algorithms=[ALGORITHM])
    second = jwt.decode(login().json()["token"], SECRET_KEY, algorithms=[ALGORITHM])
    assert first["jti"] != second["jti"]


def test_wrong_email_and_wrong_password_give_same_error(user):
    unknown_email = login(email="nadie@mail.com")
    wrong_password = login(password="incorrecta")
    assert unknown_email.status_code == wrong_password.status_code == 401
    assert unknown_email.json() == wrong_password.json()


@pytest.mark.parametrize("body", [{"email": EMAIL}, {"password": PASSWORD}])
def test_login_missing_field_is_422(body):
    assert client.post("/sessions", json=body).status_code == 422


def test_me_with_valid_token(user):
    token = login().json()["token"]
    response = client.get("/users/me", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json() == {"user_name": "juan", "user_email": EMAIL}


def test_me_without_header_is_401():
    assert client.get("/users/me").status_code == 401


def test_me_with_expired_token_is_401(user):
    payload = {
        "sub": EMAIL,
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        "jti": "x",
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    assert client.get("/users/me", headers=auth_header(token)).status_code == 401


def test_me_with_token_signed_with_other_key_is_401(user):
    payload = {
        "sub": EMAIL,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        "jti": "x",
    }
    token = jwt.encode(payload, "otra-clave-otra-clave-otra-clave-1234", algorithm=ALGORITHM)
    assert client.get("/users/me", headers=auth_header(token)).status_code == 401


def test_me_with_token_of_deleted_user_is_401():
    token = create_access_token("borrado@mail.com")
    assert client.get("/users/me", headers=auth_header(token)).status_code == 401
