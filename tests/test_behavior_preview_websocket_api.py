from uuid import uuid4
from unittest.mock import patch

import pytest

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User

from app.services.behavior_preview_websocket_service import (
    preview_connection_manager,
)


client = TestClient(app)

EMAIL = "preview-websocket@mail.com"
PASSWORD = "testpassword123"


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
def token(user):
    response = client.post(
        "/sessions",
        json={
            "email": EMAIL,
            "password": PASSWORD,
        },
    )

    assert response.status_code == 200

    return response.json()["token"]


def test_connect_preview_success(token, user):
    preview_id = uuid4()

    with patch(
        "app.api.behavior_preview_websocket.preview_belongs_to_user",
        return_value=True,
    ) as mock_belongs:

        with client.websocket_connect(
            f"/ws/behaviors/previews/{preview_id}?token={token}"
        ):
            assert preview_id in preview_connection_manager.active_connections

            assert len(
                preview_connection_manager.active_connections[preview_id]
            ) == 1

    mock_belongs.assert_called_once_with(
        preview_id=preview_id,
        user_id=user.id,
    )


def test_connect_preview_not_found(token, user):
    preview_id = uuid4()

    with patch(
        "app.api.behavior_preview_websocket.preview_belongs_to_user",
        return_value=False,
    ) as mock_belongs:

        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                f"/ws/behaviors/previews/{preview_id}?token={token}"
            ):
                pass

    assert exc.value.code == 1008

    mock_belongs.assert_called_once_with(
        preview_id=preview_id,
        user_id=user.id,
    )

    assert preview_id not in preview_connection_manager.active_connections


def test_connect_preview_without_token():
    preview_id = uuid4()

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            f"/ws/behaviors/previews/{preview_id}"
        ):
            pass

    assert exc.value.code == 1008

    assert preview_id not in preview_connection_manager.active_connections


def test_connect_preview_invalid_token():
    preview_id = uuid4()

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            f"/ws/behaviors/previews/{preview_id}?token=invalid-token"
        ):
            pass

    assert exc.value.code == 1008

    assert preview_id not in preview_connection_manager.active_connections


def test_preview_rejects_client_messages(token):
    preview_id = uuid4()

    with patch(
        "app.api.behavior_preview_websocket.preview_belongs_to_user",
        return_value=True,
    ):

        with client.websocket_connect(
            f"/ws/behaviors/previews/{preview_id}?token={token}"
        ) as websocket:

            websocket.send_text("hello")

            with pytest.raises(WebSocketDisconnect) as exc:
                websocket.receive_text()

    assert exc.value.code == 1008

    assert preview_id not in preview_connection_manager.active_connections