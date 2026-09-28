from app.game.models.match_participation import MatchParticipation


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

