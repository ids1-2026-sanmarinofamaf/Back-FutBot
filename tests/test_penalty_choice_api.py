from types import SimpleNamespace
from unittest.mock import ANY, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import matches as matches_api
from app.api.deps import get_current_user
from app.database import get_db
from app.game import penalty_session as session_module
from app.game.models.match import MatchState
from app.game.penalties import PenaltyShootout, PenaltySide
from app.game.penalty_session import PenaltySession
from app.services import match_service


URL = "/live_match/100/penalties/choices"


def override_user():
    return SimpleNamespace(id=1)


def override_db():
    return Mock()


@pytest.fixture
def api_app():
    # Mount only this router, without starting match workers.
    application = FastAPI()
    application.include_router(matches_api.router)
    application.dependency_overrides[get_db] = override_db
    return application


@pytest.fixture
def client(api_app):
    with TestClient(api_app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client(api_app, client):
    api_app.dependency_overrides[get_current_user] = override_user
    return client


@pytest.fixture
def submit_mock(monkeypatch):
    submit = Mock()
    monkeypatch.setattr(
        matches_api,
        "submit_penalty_choice",
        submit,
    )
    return submit


@pytest.mark.parametrize("side", ["LEFT", "CENTER", "RIGHT"])
def test_valid_choice_returns_204(
    authenticated_client,
    submit_mock,
    side,
):
    response = authenticated_client.post(
        URL,
        json={"turn": 1, "side": side},
    )

    assert response.status_code == 204
    assert response.content == b""
    submit_mock.assert_called_once_with(
        db=ANY,
        user_id=1,
        match_id=100,
        turn=1,
        side=PenaltySide(side),
    )


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer invalid.token.value"},
    ],
)
def test_choice_requires_valid_authentication(
    client,
    submit_mock,
    headers,
):
    response = client.post(
        URL,
        headers=headers,
        json={"turn": 1, "side": "LEFT"},
    )

    assert response.status_code == 401
    submit_mock.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"turn": 1},
        {"side": "LEFT"},
        {"turn": 0, "side": "LEFT"},
        {"turn": 7, "side": "LEFT"},
        {"turn": 1, "side": "INVALID"},
        {"turn": 1, "side": None},
    ],
)
def test_invalid_payload_returns_422(
    authenticated_client,
    submit_mock,
    payload,
):
    response = authenticated_client.post(URL, json=payload)

    assert response.status_code == 422
    submit_mock.assert_not_called()


@pytest.mark.parametrize("match_id", [0, -1, "invalid"])
def test_invalid_match_id_returns_422(
    authenticated_client,
    submit_mock,
    match_id,
):
    response = authenticated_client.post(
        f"/live_match/{match_id}/penalties/choices",
        json={"turn": 1, "side": "LEFT"},
    )

    assert response.status_code == 422
    submit_mock.assert_not_called()


@pytest.mark.parametrize(
    "error, expected_status",
    [
        (PermissionError("User has no club"), 403),
        (
            PermissionError("User is not participating in this match"),
            403,
        ),
        (LookupError("Match not found"), 404),
        (ValueError("Match has no active penalty shootout"), 409),
        (ValueError("Penalty turn is closed"), 409),
        (ValueError("Penalty turn deadline has passed"), 409),
    ],
)
def test_service_errors_become_http_responses(
    authenticated_client,
    submit_mock,
    error,
    expected_status,
):
    submit_mock.side_effect = error

    response = authenticated_client.post(
        URL,
        json={"turn": 1, "side": "LEFT"},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == str(error)
    submit_mock.assert_called_once()


def test_duplicate_request_does_not_replace_real_session_choice(
    authenticated_client,
    monkeypatch,
):
    monkeypatch.setattr(
        session_module,
        "monotonic",
        Mock(return_value=100.0),
    )

    session = PenaltySession(
        shootout=PenaltyShootout(
            club_a_id=10,
            club_b_id=20,
            kickers_a=(11, 12, 13),
            kickers_b=(21, 22, 23),
            seed=123,
        ),
        response_timeout=10.0,
    )
    session.open_turn()

    match = SimpleNamespace(
        state=MatchState.IN_PROGRESS,
        participation_a=SimpleNamespace(club_id=10),
        participation_b=SimpleNamespace(club_id=20),
        penalty_session=session,
    )

    monkeypatch.setattr(
        match_service,
        "get_match",
        Mock(return_value=match),
    )
    monkeypatch.setattr(
        match_service.club_repository,
        "get_by_user_id",
        Mock(return_value=SimpleNamespace(id=10)),
    )

    accepted = authenticated_client.post(
        URL,
        json={"turn": 1, "side": "LEFT"},
    )
    duplicate = authenticated_client.post(
        URL,
        json={"turn": 1, "side": "RIGHT"},
    )

    assert accepted.status_code == 204
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == (
        "Club has already submitted a choice for this turn"
    )

    assert session.choices == {10: PenaltySide.LEFT}
    assert not session.responses_received.is_set()
    assert session.shootout.turn == 0
