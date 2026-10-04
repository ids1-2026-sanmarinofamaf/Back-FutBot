import pytest

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.api.deps import get_current_user

from app.models.user import User
from app.models.club import Club
from app.models.player import Player
from app.models.behavior import Behavior

from app.models.roster import Roster, Formation
from app.models.player_on_roster import (
    PlayerOnRoster,
    RosterSlot,
)

from app.models.friendly_game import (
    FriendlyGame,
    FriendlyGameState,
)

from app.models.friendly_game_participation import (
    FriendlyGameParticipation,
    FriendlyGameRole,
)


client = TestClient(app)

# Helpers

def create_user_with_club(db, email, club_name):
    user = User(
        email=email,
        hash_passwd="test_hash",
    )

    db.add(user)
    db.flush()

    club = Club(
        user_id=user.id,
        name=club_name,
    )

    db.add(club)
    db.flush()

    return user, club


def create_players(db, club_id):
    players = []

    for i in range(6):
        player = Player(
            club_id=club_id,
            name=f"Player {i + 1}",
            power=60,
            agility=60,
            control=60,
            speed=60,
            strength=60,
        )

        db.add(player)
        players.append(player)

    db.flush()

    return players


def create_behaviors(db, club_id):
    behaviors = []

    for i in range(3):
        behavior = Behavior(
            club_id=club_id,
            name=f"Behavior {i + 1}",
            code="def play(): pass",
        )

        db.add(behavior)
        behaviors.append(behavior)

    db.flush()

    return behaviors


def create_creator_participation(
    db,
    friendly_game,
    creator_club,
):
    creator_roster = Roster(
        club_id=creator_club.id,
        formation=Formation.DEFENSIVE,
    )

    db.add(creator_roster)
    db.flush()

    participation = FriendlyGameParticipation(
        friendly_game_id=friendly_game.id,
        club_id=creator_club.id,
        roster_id=creator_roster.id,
        role=FriendlyGameRole.CREATOR,
    )

    db.add(participation)
    db.flush()

    return participation


def valid_join_body(players, behaviors):
    return {
        "roster": {
            "formation": "offensive",
            "players": [
                {
                    "player_id": players[0].id,
                    "is_starter": True,
                    "slot": "left",
                    "initial_behavior_id": behaviors[0].id,
                },
                {
                    "player_id": players[1].id,
                    "is_starter": True,
                    "slot": "center",
                    "initial_behavior_id": behaviors[1].id,
                },
                {
                    "player_id": players[2].id,
                    "is_starter": True,
                    "slot": "right",
                    "initial_behavior_id": behaviors[2].id,
                },
                {
                    "player_id": players[3].id,
                    "is_starter": False,
                    "slot": None,
                    "initial_behavior_id": None,
                },
                {
                    "player_id": players[4].id,
                    "is_starter": False,
                    "slot": None,
                    "initial_behavior_id": None,
                },
                {
                    "player_id": players[5].id,
                    "is_starter": False,
                    "slot": None,
                    "initial_behavior_id": None,
                },
            ],
        }
    }



# Fixture para dejar limpia la BD entre estos tests

@pytest.fixture(autouse=True)
def clean_join_database():
    db = SessionLocal()

    try:
        db.query(PlayerOnRoster).delete()
        db.query(FriendlyGameParticipation).delete()
        db.query(Roster).delete()
        db.query(FriendlyGame).delete()
        db.query(Behavior).delete()
        db.query(Player).delete()
        db.query(Club).delete()
        db.query(User).delete()

        db.commit()

        yield

    finally:
        db.rollback()

        db.query(PlayerOnRoster).delete()
        db.query(FriendlyGameParticipation).delete()
        db.query(Roster).delete()
        db.query(FriendlyGame).delete()
        db.query(Behavior).delete()
        db.query(Player).delete()
        db.query(Club).delete()
        db.query(User).delete()

        db.commit()
        db.close()

        app.dependency_overrides.clear()


# ---------------------------------------------------------
# 1. JOIN válido
# ---------------------------------------------------------

def test_join_valid_friendly_game_persists_participation_and_roster():
    db = SessionLocal()

    try:
        # Creador
        _, creator_club = create_user_with_club(
            db,
            "creator@test.com",
            "Creator Club",
        )

        # Usuario que se va a unir
        guest_user, guest_club = create_user_with_club(
            db,
            "guest@test.com",
            "Guest Club",
        )

        guest_players = create_players(
            db,
            guest_club.id,
        )

        guest_behaviors = create_behaviors(
            db,
            guest_club.id,
        )

        # Amistoso disponible
        friendly_game = FriendlyGame(
            duration=1000,
            creator_id=creator_club.id,
            state=FriendlyGameState.POR_COMENZAR,
        )

        db.add(friendly_game)
        db.flush()

        create_creator_participation(
            db,
            friendly_game,
            creator_club,
        )

        db.commit()

        friendly_game_id = friendly_game.id
        guest_user_id = guest_user.id
        guest_club_id = guest_club.id

        body = valid_join_body(
            guest_players,
            guest_behaviors,
        )

    finally:
        db.close()

    # Simulamos usuario autenticado.
    app.dependency_overrides[get_current_user] = (
        lambda: SimpleNamespace(id=guest_user_id)
    )

    # Petición REAL al endpoint.
    response = client.post(
        f"/friendly_games/{friendly_game_id}/users",
        json=body,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["friendly_game_id"] == friendly_game_id

    # Verificamos realmente la BD.
    verify_db = SessionLocal()

    try:
        participation = verify_db.get(
            FriendlyGameParticipation,
            data["participation_id"],
        )

        roster = verify_db.get(
            Roster,
            data["roster_id"],
        )

        assert participation is not None
        assert roster is not None

        # Participación registrada correctamente.
        assert participation.friendly_game_id == friendly_game_id
        assert participation.club_id == guest_club_id
        assert participation.role == FriendlyGameRole.GUEST
        assert participation.roster_id == roster.id

        # Plantilla registrada correctamente.
        assert roster.club_id == guest_club_id
        assert roster.formation == Formation.OFFENSIVE

        assert len(roster.players) == 6

        starters = [
            player
            for player in roster.players
            if player.is_starter
        ]

        substitutes = [
            player
            for player in roster.players
            if not player.is_starter
        ]

        assert len(starters) == 3
        assert len(substitutes) == 3

        assert {
            player.slot
            for player in starters
        } == {
            RosterSlot.LEFT,
            RosterSlot.CENTER,
            RosterSlot.RIGHT,
        }

    finally:
        verify_db.close()


# 2. Amistoso lleno

def test_join_full_friendly_game_is_rejected():
    db = SessionLocal()

    try:
        _, creator_club = create_user_with_club(
            db,
            "creator@test.com",
            "Creator Club",
        )

        _, existing_guest_club = create_user_with_club(
            db,
            "existing@test.com",
            "Existing Guest",
        )

        new_guest_user, new_guest_club = create_user_with_club(
            db,
            "newguest@test.com",
            "New Guest",
        )

        new_guest_players = create_players(
            db,
            new_guest_club.id,
        )

        new_guest_behaviors = create_behaviors(
            db,
            new_guest_club.id,
        )

        friendly_game = FriendlyGame(
            duration=1000,
            creator_id=creator_club.id,
            state=FriendlyGameState.POR_COMENZAR,
        )

        db.add(friendly_game)
        db.flush()

        create_creator_participation(
            db,
            friendly_game,
            creator_club,
        )

        # Segunda participación: el cupo ya queda completo.
        existing_guest_roster = Roster(
            club_id=existing_guest_club.id,
            formation=Formation.DEFENSIVE,
        )

        db.add(existing_guest_roster)
        db.flush()

        db.add(
            FriendlyGameParticipation(
                friendly_game_id=friendly_game.id,
                club_id=existing_guest_club.id,
                roster_id=existing_guest_roster.id,
                role=FriendlyGameRole.GUEST,
            )
        )

        db.commit()

        friendly_game_id = friendly_game.id
        new_guest_user_id = new_guest_user.id

        body = valid_join_body(
            new_guest_players,
            new_guest_behaviors,
        )

        rosters_before = db.query(Roster).count()

        participations_before = (
            db.query(FriendlyGameParticipation).count()
        )

    finally:
        db.close()

    app.dependency_overrides[get_current_user] = (
        lambda: SimpleNamespace(id=new_guest_user_id)
    )

    response = client.post(
        f"/friendly_games/{friendly_game_id}/users",
        json=body,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Friendly game is full"

    # Comprobamos que no se haya guardado nada.
    verify_db = SessionLocal()

    try:
        assert (
            verify_db.query(Roster).count()
            == rosters_before
        )

        assert (
            verify_db.query(
                FriendlyGameParticipation
            ).count()
            == participations_before
        )

    finally:
        verify_db.close()

# 3. Plantilla inválida/incompleta

def test_join_with_invalid_roster_is_rejected_without_changes():
    db = SessionLocal()

    try:
        _, creator_club = create_user_with_club(
            db,
            "creator@test.com",
            "Creator Club",
        )

        guest_user, guest_club = create_user_with_club(
            db,
            "guest@test.com",
            "Guest Club",
        )

        guest_players = create_players(
            db,
            guest_club.id,
        )

        guest_behaviors = create_behaviors(
            db,
            guest_club.id,
        )

        friendly_game = FriendlyGame(
            duration=1000,
            creator_id=creator_club.id,
            state=FriendlyGameState.POR_COMENZAR,
        )

        db.add(friendly_game)
        db.flush()

        create_creator_participation(
            db,
            friendly_game,
            creator_club,
        )

        db.commit()

        friendly_game_id = friendly_game.id
        guest_user_id = guest_user.id

        state_before = friendly_game.state

        rosters_before = db.query(Roster).count()

        participations_before = (
            db.query(FriendlyGameParticipation).count()
        )

        body = valid_join_body(
            guest_players,
            guest_behaviors,
        )

        # Hacemos inválida la plantilla:
        # queda con sólo 5 jugadores.
        body["roster"]["players"].pop()

    finally:
        db.close()

    app.dependency_overrides[get_current_user] = (
        lambda: SimpleNamespace(id=guest_user_id)
    )

    response = client.post(
        f"/friendly_games/{friendly_game_id}/users",
        json=body,
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "A roster must have exactly 6 players"
    )

    # Verificamos que no haya modificaciones.
    verify_db = SessionLocal()

    try:
        game_after = verify_db.get(
            FriendlyGame,
            friendly_game_id,
        )

        assert game_after is not None

        # El partido sigue exactamente en el mismo estado.
        assert game_after.state == state_before

        # No se creó ninguna plantilla nueva.
        assert (
            verify_db.query(Roster).count()
            == rosters_before
        )

        # No se creó ninguna participación nueva.
        assert (
            verify_db.query(
                FriendlyGameParticipation
            ).count()
            == participations_before
        )

    finally:
        verify_db.close()