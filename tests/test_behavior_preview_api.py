from uuid import uuid4
from unittest.mock import patch, ANY

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.behavior_preview import (
    BehaviorPreviewCreate,
    BehaviorPreviewCreateResponse,
)


client = TestClient(app)

EMAIL = "preview-endpoints@mail.com"
PASSWORD = "testpassword123"

VALID_DATA = {
    "code": "def play():\n    return wait()",
    "behavior_teammate_1": 1,
    "behavior_teammate_2": 2,
}


def test_create_preview_with_valid_data():
    preview = BehaviorPreviewCreate(**VALID_DATA)

    assert preview.model_dump() == VALID_DATA


@pytest.mark.parametrize(
    "missing_field",
    [
        "code",
        "behavior_teammate_1",
        "behavior_teammate_2",
    ],
)
def test_create_preview_rejects_missing_fields(missing_field):
    data = VALID_DATA.copy()
    del data[missing_field]

    with pytest.raises(ValidationError):
        BehaviorPreviewCreate(**data)


@pytest.mark.parametrize("invalid_code", ["", None, 123])
def test_create_preview_rejects_invalid_code(invalid_code):
    data = {**VALID_DATA, "code": invalid_code}

    with pytest.raises(ValidationError):
        BehaviorPreviewCreate(**data)


@pytest.mark.parametrize(
    "field",
    ["behavior_teammate_1", "behavior_teammate_2"],
)
@pytest.mark.parametrize(
    "invalid_value",
    [0, -1, None, "invalid", 1.5],
)
def test_create_preview_rejects_invalid_behavior_ids(
    field,
    invalid_value,
):
    data = {**VALID_DATA, field: invalid_value}

    with pytest.raises(ValidationError):
        BehaviorPreviewCreate(**data)


def test_create_preview_response():
    preview_id = uuid4()

    response = BehaviorPreviewCreateResponse(
        preview_id=preview_id,
    )

    assert response.model_dump(mode="json") == {
        "preview_id": str(preview_id),
    }


@pytest.mark.parametrize(
    "invalid_uuid",
    ["", "invalid-uuid", None, 123],
)
def test_create_preview_response_rejects_invalid_uuid(invalid_uuid):
    with pytest.raises(ValidationError):
        BehaviorPreviewCreateResponse(preview_id=invalid_uuid)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def user(db):
    user = User(
        email=EMAIL,
        hash_passwd=get_password_hash(PASSWORD),
    )

    db.add(user)
    db.commit()

    yield user

    db.delete(user)
    db.commit()


@pytest.fixture
def headers(user):
    response = client.post(
        "/sessions",
        json={
            "email": EMAIL,
            "password": PASSWORD,
        },
    )

    assert response.status_code == 200

    return {
        "Authorization": f"Bearer {response.json()['token']}"
    }


def test_create_preview_returns_201(headers, user):
    preview_id = uuid4()

    with patch(
        "app.api.behavior_preview.create_preview",
        return_value=preview_id,
    ) as mock_create:

        response = client.post(
            "/clubes/me/behaviors/previews",
            json=VALID_DATA,
            headers=headers,
        )

    assert response.status_code == 201
    assert response.json() == {
        "preview_id": str(preview_id),
    }
    mock_create.assert_called_once_with(
        db=ANY,
        user_id=user.id,
        code=VALID_DATA["code"],
        behavior_teammate_1=VALID_DATA["behavior_teammate_1"],
        behavior_teammate_2=VALID_DATA["behavior_teammate_2"],
    )


def test_create_preview_invalid_default_returns_400(headers):
    with patch(
        "app.api.behavior_preview.create_preview",
        side_effect=ValueError("Invalid default behavior"),
    ):
        response = client.post(
            "/clubes/me/behaviors/previews",
            json=VALID_DATA,
            headers=headers,
        )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid default behavior",
    }


def test_stop_preview_returns_204(headers):
    preview_id = uuid4()

    with patch(
        "app.api.behavior_preview.stop_preview",
    ) as mock_stop:
        response = client.delete(
            f"/clubes/me/behaviors/previews/{preview_id}",
            headers=headers,
        )

    assert response.status_code == 204
    assert response.content == b""
    mock_stop.assert_called_once()


def test_stop_preview_not_found_returns_404(headers):
    preview_id = uuid4()

    with patch(
        "app.api.behavior_preview.stop_preview",
        side_effect=LookupError("Preview not found"),
    ):
        response = client.delete(
            f"/clubes/me/behaviors/previews/{preview_id}",
            headers=headers,
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Preview not found",
    }


def test_create_preview_without_auth_returns_401():
    response = client.post(
        "/clubes/me/behaviors/previews",
        json=VALID_DATA,
    )

    assert response.status_code == 401


def test_stop_preview_without_auth_returns_401():
    response = client.delete(
        f"/clubes/me/behaviors/previews/{uuid4()}",
    )

    assert response.status_code == 401