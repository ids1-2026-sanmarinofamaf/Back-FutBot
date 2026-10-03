import pytest

from app.models.friendly_game import (FriendlyGame, FriendlyGameState)
from app.models.friendly_game_participation import (
    FriendlyGameParticipation,
    FriendlyGameRole,
)


def make_participation(
    club_id: int,
    roster_id: int,
    role: FriendlyGameRole = FriendlyGameRole.GUEST,
):
    return FriendlyGameParticipation(
        club_id=club_id,
        roster_id=roster_id,
        role=role,
    )


def make_game(
    duration: int = 10,
    creator_id: int = 1,
    state: FriendlyGameState = FriendlyGameState.POR_COMENZAR,
) -> FriendlyGame:
    return FriendlyGame(
        duration=duration,
        creator_id=creator_id,
        state=state,
    )


def test_friendly_game_contains_required_data():
    game = make_game()


    assert game.duration == 10
    assert game.creator_id == 1
    assert game.state == FriendlyGameState.POR_COMENZAR


def test_friendly_game_participation_stores_club_and_roster_ids():
    participation = make_participation(3, 7)


    assert participation.club_id == 3
    assert participation.roster_id == 7


def test_friendly_game_participation_stores_role():
    participation = make_participation(
        3,
        7,
        FriendlyGameRole.CREATOR,
    )


    assert participation.role == FriendlyGameRole.CREATOR


def test_friendly_game_can_have_two_participants():
    game = make_game()


    game.participations = [
        make_participation(
            1,
            10,
            FriendlyGameRole.CREATOR,
        ),
        make_participation(
            2,
            20,
            FriendlyGameRole.GUEST,
        ),
    ]


    assert len(game.participations) == 2
    assert game.participations[0].club_id == 1
    assert game.participations[0].roster_id == 10
    assert game.participations[0].role == FriendlyGameRole.CREATOR
    assert game.participations[1].club_id == 2
    assert game.participations[1].roster_id == 20
    assert game.participations[1].role == FriendlyGameRole.GUEST


def test_friendly_game_can_change_state():
    game = make_game()


    game.state = FriendlyGameState.JUGANDO


    assert game.state == FriendlyGameState.JUGANDO


    game.state = FriendlyGameState.FINALIZADO


    assert game.state == FriendlyGameState.FINALIZADO