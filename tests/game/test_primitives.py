from app.game.primitives import distance

def test_distance_between_two_points():
    assert distance((0.0, 0.0), (3.0, 4.0)) == 5.0

def test_distance_between_same_position():
    assert distance((2.0, 3.0), (2.0, 3.0)) == 0.0