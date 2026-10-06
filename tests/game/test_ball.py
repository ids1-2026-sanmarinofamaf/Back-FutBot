from app.game.models.ball import Ball


def test_ball_stores_current_state():
    ball = Ball(
        position=(20.0, 10.0),
        velocity=(2.0, -1.0),
    )

    assert ball.position == (20.0, 10.0)
    assert ball.velocity == (2.0, -1.0)