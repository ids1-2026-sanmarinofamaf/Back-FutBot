from app.game.models.match_participation import MatchParticipation
from conftest import make_player
import pytest


def test_participation_has_three_starters_and_three_substitutes(six_players):
    players = six_players

    participation = MatchParticipation(
        club_id=1,
        roster_id=1,
        players=players,
    )

    # we are looking for the starters and the substitutes.
    starters = []
    substitutes = []

    for player in participation.players:
        if player.is_on_field:
            starters.append(player)
        else:
            substitutes.append(player)

    assert len(participation.players) == 6
    assert len(starters) == 3
    assert len(substitutes) == 3

def test_match_participation_rejects_more_than_six_players(six_players):
    players = six_players + [make_player(7, False)]
    with pytest.raises(ValueError,          # we check that match participation throws valueerror
        match="A match participation must have exactly 6 players",
    ):
        MatchParticipation(
            club_id=1,
            roster_id=1,
            players=players,
        )

def test_match_participation_rejects_wrong_number_of_starters(
    six_players,
):
    six_players[3].is_on_field = True

    with pytest.raises(ValueError,
        match="A match participation must have exactly 3 starters",
    ):
        MatchParticipation(
            club_id=1,
            roster_id=1,
            players=six_players,
        )


def test_match_participation_rejects_duplicate_players(
    six_players,
):
    six_players[5].player_id = six_players[0].player_id

    with pytest.raises(ValueError,
        match="A match participation cannot contain duplicate players",
    ):
        MatchParticipation(
            club_id=1,
            roster_id=1,
            players=six_players,
        )