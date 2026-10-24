import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.core.ws_manager import manager
from app.database import SessionLocal
from app.main import app
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.league import League, LeaguePrivacy, LeagueState
from app.models.league_participation import LeagueParticipation
from app.models.player import Player
from app.models.player_on_roster import PlayerOnRoster
from app.models.roster import Roster, Formation
from app.models.user import User
from app.services.league_service import ClubNotFound


client = TestClient(app)

EMAIL = "league@mail.com"
PASSWORD = "secreta123"


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
        club=Club(name="league-club"),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    yield user

    db.rollback()
    db.query(LeagueParticipation).delete()
    db.query(League).delete()
    db.query(PlayerOnRoster).delete()
    db.query(Roster).delete()
    db.query(Player).delete()
    db.query(Behavior).filter(Behavior.is_default.is_(False)).delete()
    db.query(Club).delete()
    db.query(User).delete()
    db.commit()


@pytest.fixture
def players(db, user):
    players = [
        Player(
            club_id=user.club.id,
            name=f"Player {i + 1}",
            power=60,
            agility=60,
            control=60,
            speed=60,
            strength=60,
        )
        for i in range(6)
    ]

    db.add_all(players)
    db.commit()

    return players


@pytest.fixture
def behavior(db, user):
    behavior = Behavior(
        club_id=user.club.id,
        name="Behavior 1",
        code="def play(): pass",
    )

    db.add(behavior)
    db.commit()

    return behavior


def login():
    response = client.post(
        "/sessions",
        json={
            "email": EMAIL,
            "password": PASSWORD,
        },
    )

    return response.json()["token"]


def auth_header(token):
    return {
        "Authorization": f"Bearer {token}"
    }


def roster_body(players, behavior):
    slots = ["left", "center", "right"]

    return {
        "formation": "offensive",
        "players": [
            {
                "player_id": player.id,
                "is_starter": i < 3,
                "slot": slots[i] if i < 3 else None,
                "initial_behavior_id": behavior.id if i < 3 else None,
            }
            for i, player in enumerate(players)
        ],
    }


def valid_body(players, behavior):
    return {
        "nombre": "Liga1",
        "duracion_partido": 10,
        "max_usuarios": 8,
        "es_privada": False,
        "password": "",
        "roster": roster_body(players, behavior),
    }


def post_league(body, token=None):
    headers = auth_header(token if token else login())
    return client.post("/leagues", json=body, headers=headers)


def count(db, model):
    db.expire_all()
    return db.query(model).count()


def assert_nothing_saved(db):
    assert count(db, League) == 0
    assert count(db, Roster) == 0
    assert count(db, LeagueParticipation) == 0


# a valid body creates the league with the same values and returns 201 with its id
def test_create_league_success(user, db, players, behavior):
    response = post_league(valid_body(players, behavior))

    assert response.status_code == 201
    league_id = response.json()["id_liga"]

    league = db.get(League, league_id)
    assert league is not None
    assert league.name == "Liga1"
    assert league.match_duration == 10
    assert league.max_clubs == 8
    assert league.privacy == LeaguePrivacy.PUBLICA
    assert league.password_hash is None
    assert league.state == LeagueState.POR_COMENZAR
    # the league belongs to the club of the user that made the request
    assert league.creator_id == user.club.id


# the creator is automatically registered as participant of the league
def test_create_league_registers_creator_participation(user, db, players, behavior):
    response = post_league(valid_body(players, behavior))
    league_id = response.json()["id_liga"]

    db.expire_all()
    participations = (
        db.query(LeagueParticipation)
        .filter(LeagueParticipation.league_id == league_id)
        .all()
    )

    assert len(participations) == 1
    participation = participations[0]
    assert participation.club_id == user.club.id
    assert participation.points == 0
    assert participation.matches_played == 0


# the participation is associated with the roster sent in the body
def test_create_league_associates_roster(user, db, players, behavior):
    body = valid_body(players, behavior)

    response = post_league(body)
    league_id = response.json()["id_liga"]

    db.expire_all()
    participation = (
        db.query(LeagueParticipation)
        .filter(LeagueParticipation.league_id == league_id)
        .one()
    )
    roster = participation.roster

    assert roster.club_id == user.club.id
    assert roster.formation == Formation.OFFENSIVE
    assert len(roster.players) == 6

    sent = {p["player_id"]: p for p in body["roster"]["players"]}
    for player_on_roster in roster.players:
        expected = sent[player_on_roster.player_id]
        assert player_on_roster.is_starter == expected["is_starter"]
        assert player_on_roster.initial_behavior_id == expected["initial_behavior_id"]


# a private league stores the hashed password, never the plain one
def test_create_private_league_hashes_password(user, db, players, behavior):
    body = valid_body(players, behavior)
    body["es_privada"] = True
    body["password"] = "clave123"

    response = post_league(body)

    assert response.status_code == 201

    league = db.get(League, response.json()["id_liga"])
    assert league.privacy == LeaguePrivacy.PRIVADA
    assert league.password_hash != "clave123"
    assert verify_password("clave123", league.password_hash)


# a body missing any required field returns 400 and does not create the league
@pytest.mark.parametrize(
    "missing_field",
    ["nombre", "duracion_partido", "max_usuarios", "es_privada", "roster"],
)
def test_create_league_missing_field_returns_400(user, db, players, behavior, missing_field):
    body = valid_body(players, behavior)
    del body[missing_field]

    response = post_league(body)

    assert response.status_code == 400
    assert_nothing_saved(db)


# an empty name returns 400
def test_create_league_empty_name_returns_400(user, db, players, behavior):
    body = valid_body(players, behavior)
    body["nombre"] = ""

    response = post_league(body)

    assert response.status_code == 400
    assert_nothing_saved(db)


# a private league without password returns 400
def test_create_private_league_without_password_returns_400(user, db, players, behavior):
    body = valid_body(players, behavior)
    body["es_privada"] = True
    body["password"] = ""

    response = post_league(body)

    assert response.status_code == 400
    assert_nothing_saved(db)


# a public league with a password returns 400
def test_create_public_league_with_password_returns_400(user, db, players, behavior):
    body = valid_body(players, behavior)
    body["password"] = "clave123"

    response = post_league(body)

    assert response.status_code == 400
    assert_nothing_saved(db)


# a roster with less than 6 players returns 400 and nothing is saved
def test_create_league_incomplete_roster_returns_400(user, db, players, behavior):
    body = valid_body(players, behavior)
    body["roster"]["players"].pop()

    response = post_league(body)

    assert response.status_code == 400
    assert response.json()["detail"] == "A roster must have exactly 6 players"
    assert_nothing_saved(db)


# a roster with a player of another club returns 400 and nothing is saved
def test_create_league_player_of_other_club_returns_400(user, db, players, behavior):
    other_user = User(
        email="other@mail.com",
        hash_passwd="test_hash",
        club=Club(name="other-club"),
    )
    db.add(other_user)
    db.flush()
    other_player = Player(
        club_id=other_user.club.id,
        name="Other player",
        power=60,
        agility=60,
        control=60,
        speed=60,
        strength=60,
    )
    db.add(other_player)
    db.commit()

    body = valid_body(players, behavior)
    body["roster"]["players"][0]["player_id"] = other_player.id

    response = post_league(body)

    assert response.status_code == 400
    assert response.json()["detail"] == "Player does not belong to user's club"
    assert_nothing_saved(db)


# if creating the participation fails, league and roster are rolled back
def test_create_league_rollback_when_participation_fails(user, db, players, behavior):
    token = login()

    with patch(
        "app.services.league_service.league_participation_repository.create_participation",
        side_effect=RuntimeError("db error"),
    ):
        with pytest.raises(RuntimeError):
            post_league(valid_body(players, behavior), token)

    assert_nothing_saved(db)


# a request without token returns 401
def test_create_league_without_token_returns_401(user, db, players, behavior):
    response = client.post("/leagues", json=valid_body(players, behavior))

    assert response.status_code == 401
    assert_nothing_saved(db)


# a user without club returns 404
def test_create_league_without_club_returns_404(user, db, players, behavior):
    with patch("app.api.leagues.create_league", side_effect=ClubNotFound("Club does not exist")):
        response = post_league(valid_body(players, behavior))

    assert response.status_code == 404
    assert response.json() == {"detail": "Club does not exist"}


# ---------------------------------------------------------------------------
# Broadcast to the session websocket (ws/sessions)
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_manager():
    # empty the global manager so connections from other tests don't receive messages
    manager.active.clear()
    yield
    manager.active.clear()


# a successful creation broadcasts the leagues once, with the same db session
def test_create_league_success_broadcasts_leagues(user, db, players, behavior):
    token = login()

    with patch(
        "app.api.leagues.session_websocket_service.broadcast_leagues",
        new_callable=AsyncMock,
    ) as mock_broadcast:
        response = post_league(valid_body(players, behavior), token)

    assert response.status_code == 201
    mock_broadcast.assert_awaited_once()
    # the broadcast reads the leagues with the session of the request
    assert isinstance(mock_broadcast.await_args.args[0], Session)


# an invalid roster (400) does not broadcast
def test_create_league_invalid_roster_does_not_broadcast(user, db, players, behavior):
    token = login()
    body = valid_body(players, behavior)
    body["roster"]["players"].pop()

    with patch(
        "app.api.leagues.session_websocket_service.broadcast_leagues",
        new_callable=AsyncMock,
    ) as mock_broadcast:
        response = post_league(body, token)

    assert response.status_code == 400
    mock_broadcast.assert_not_awaited()


# a user without club (404) does not broadcast
def test_create_league_without_club_does_not_broadcast(user, db, players, behavior):
    token = login()

    with (
        patch(
            "app.api.leagues.create_league",
            side_effect=ClubNotFound("Club does not exist"),
        ),
        patch(
            "app.api.leagues.session_websocket_service.broadcast_leagues",
            new_callable=AsyncMock,
        ) as mock_broadcast,
    ):
        response = post_league(valid_body(players, behavior), token)

    assert response.status_code == 404
    mock_broadcast.assert_not_awaited()


# a body that fails the schema validation never reaches the endpoint, so no broadcast
def test_create_league_invalid_body_does_not_broadcast(user, db, players, behavior):
    token = login()
    body = valid_body(players, behavior)
    body["nombre"] = ""

    with patch(
        "app.api.leagues.session_websocket_service.broadcast_leagues",
        new_callable=AsyncMock,
    ) as mock_broadcast:
        response = post_league(body, token)

    assert response.status_code == 400
    mock_broadcast.assert_not_awaited()


# fake websocket that stores the JSON messages it receives
class FakeWebSocket:
    def __init__(self):
        self.sent = []

    async def accept(self):
        pass

    async def send_json(self, message):
        self.sent.append(message)


# end to end: a client connected to ws/sessions receives the new league from the db
def test_create_league_connected_client_receives_new_league(
    user, db, players, behavior, clean_manager
):
    connection = FakeWebSocket()
    asyncio.run(manager.connect(user.id, connection))

    response = post_league(valid_body(players, behavior))

    assert response.status_code == 201
    league_id = response.json()["id_liga"]

    assert connection.sent == [
        {
            "leagues": [
                {
                    "league_id": league_id,
                    "name": "Liga1",
                    # the creator is already participating
                    "current_participants": 1,
                    "capacity": 8,
                    "privacy": "PUBLICA",
                    "state": "POR_COMENZAR",
                }
            ]
        }
    ]


# the broadcast reaches every connected client, not only the creator
def test_create_league_broadcast_reaches_every_connection(
    user, db, players, behavior, clean_manager
):
    creator_connection = FakeWebSocket()
    other_connection = FakeWebSocket()
    asyncio.run(manager.connect(user.id, creator_connection))
    asyncio.run(manager.connect(user.id + 1, other_connection))

    response = post_league(valid_body(players, behavior))

    assert response.status_code == 201
    assert len(creator_connection.sent) == 1
    assert other_connection.sent == creator_connection.sent


# a failed creation sends nothing to the connected clients
def test_create_league_failure_sends_nothing_to_connections(
    user, db, players, behavior, clean_manager
):
    connection = FakeWebSocket()
    asyncio.run(manager.connect(user.id, connection))

    body = valid_body(players, behavior)
    body["roster"]["players"].pop()

    response = post_league(body)

    assert response.status_code == 400
    assert connection.sent == []
