import base64
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.security import verify_password
from app.database import SessionLocal
from app.main import app
from app.models.club import DEFAULT_AVATAR, Club
from app.models.user import User
from app.repositories import user_repository

client = TestClient(app)

EMAIL = "nuevo@mail.com"
PASSWORD = "secreta123"
PNG_AVATAR = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100).decode()


def valid_body(**overrides):
    body = {
        "email": EMAIL,
        "password": PASSWORD,
        "club_name": "Los Robots",
        "avatar": PNG_AVATAR,
    }
    body.update(overrides)
    return body


@pytest.fixture(autouse=True)
def clean_users():
    yield
    db = SessionLocal()
    db.query(Club).delete()
    db.query(User).delete()
    db.commit()
    db.close()


def count_users():
    db = SessionLocal()
    try:
        return db.query(User).count(), db.query(Club).count()
    finally:
        db.close()


def test_register_ok_returns_201():
    response = client.post("/users", json=valid_body())
    assert response.status_code == 201
    assert response.json() == {"user_name": "Los Robots", "user_email": EMAIL}


def test_registered_user_can_be_retrieved_by_email():
    client.post("/users", json=valid_body())
    db = SessionLocal()
    try:
        user = user_repository.get_by_email(db, EMAIL)
        assert user is not None
        assert user.club.name == "Los Robots"
        assert user.club.avatar == PNG_AVATAR
    finally:
        db.close()


def test_password_is_stored_hashed():
    client.post("/users", json=valid_body())
    db = SessionLocal()
    try:
        user = user_repository.get_by_email(db, EMAIL)
        assert user.hash_passwd != PASSWORD
        assert PASSWORD not in user.hash_passwd
        assert verify_password(PASSWORD, user.hash_passwd)
    finally:
        db.close()


def test_registered_user_can_login():
    client.post("/users", json=valid_body())
    response = client.post("/sessions", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200


def test_duplicate_email_returns_409_and_does_not_create_another_user():
    client.post("/users", json=valid_body())
    response = client.post("/users", json=valid_body(club_name="Otro Club"))
    assert response.status_code == 409
    assert count_users() == (1, 1)


@pytest.mark.parametrize("avatar", [None, ""])
def test_register_without_avatar_uses_default(avatar):
    response = client.post("/users", json=valid_body(avatar=avatar))
    assert response.status_code == 201
    db = SessionLocal()
    try:
        assert user_repository.get_by_email(db, EMAIL).club.avatar == DEFAULT_AVATAR
    finally:
        db.close()


def test_register_with_avatar_omitted_uses_default():
    body = valid_body()
    del body["avatar"]
    response = client.post("/users", json=body)
    assert response.status_code == 201
    db = SessionLocal()
    try:
        assert user_repository.get_by_email(db, EMAIL).club.avatar == DEFAULT_AVATAR
    finally:
        db.close()


@pytest.mark.parametrize("missing", ["email", "password", "club_name"])
def test_incomplete_body_returns_422(missing):
    body = valid_body()
    del body[missing]
    response = client.post("/users", json=body)
    assert response.status_code == 422
    assert count_users() == (0, 0)


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "no-es-un-email"},
        {"password": "corta"},
        {"password": "con espacios 123"},
        {"password": "a" * 31},
        {"club_name": "ab"},
        {"club_name": "Club 2"},
        {"avatar": "esto no es base64!"},
        {"avatar": base64.b64encode(b"GIF89a....").decode()},
    ],
)
def test_invalid_data_returns_422(overrides):
    response = client.post("/users", json=valid_body(**overrides))
    assert response.status_code == 422
    assert count_users() == (0, 0)


def test_failed_persistence_leaves_no_residue():
    real_create = user_repository.create

    def create_then_fail(db, user):
        # El usuario y el club ya se enviaron a la base (flush) cuando ocurre el fallo
        real_create(db, user)
        raise OperationalError("INSERT", {}, Exception("db caida"))

    with patch("app.repositories.user_repository.create", side_effect=create_then_fail):
        with pytest.raises(OperationalError):
            client.post("/users", json=valid_body())
    assert count_users() == (0, 0)
