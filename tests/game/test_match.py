from app.game.models.ball import Ball
from app.game.models.match import Match, MatchState
from app.game.models.match_participation import MatchParticipation



def test_match_has_two_participations(six_players):
    # create 2 list of 6 players
    players_a = six_players

    players_b = six_players

    # create 2 match_participation
    participation_a = MatchParticipation(
        club_id=1,
        roster_id=1,
        players=players_a,
    )

    participation_b = MatchParticipation(
        club_id=2,
        roster_id=2,
        players=players_b,
    )

    # create ball
    ball = Ball(
        position=(20.0, 10.0),
        velocity=(2.0, -1.0),
    )

    # create a match with what was previously defined
    match = Match(
        match_id=1,
        participation_a=participation_a,
        participation_b=participation_b,
        ball=ball,
        duration_ticks=1000,
    )

    assert match.participation_a is participation_a
    assert match.participation_b is participation_b
    assert match.participation_a != match.participation_b
    assert match.current_tick == 0
    assert match.state == MatchState.NOT_STARTED

def test_complete_match_runtime_state(six_players):

    players_a = six_players

    players_b = six_players

    participation_a = MatchParticipation(
        club_id=1,
        roster_id=1,
        players=players_a,
    )

    participation_b = MatchParticipation(
        club_id=2,
        roster_id=2,
        players=players_b,
    )

    match = Match(
        match_id=1,
        participation_a=participation_a,
        participation_b=participation_b,
        ball=Ball(
            position=(20.0, 10.0),
            velocity=(2.0, -1.0),
        ),
        duration_ticks=1000,
    )

    #   we verify that everything defined is correctly saved within the match object.
    assert len(match.participation_a.players) == 6
    assert len(match.participation_b.players) == 6
    assert match.ball.position == (20.0, 10.0)
    assert match.ball.velocity == (2.0, -1.0)
    assert match.duration_ticks == 1000
    assert match.current_tick == 0
    assert match.state == MatchState.NOT_STARTED