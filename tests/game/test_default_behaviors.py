from app.game import primitives
from app.game.types import Side
from app.game.constants import(
    LEFT_GOAL,
    RIGHT_GOAL,
)
from app.game.models.actions import MoveAction, KickAction, WaitAction
from app.game.context import set_current_context, clear_current_context
from app.game.default_behaviors import (
    ATTACKER_CODE,
    DEFENDER_CODE,
    MIDFIELDER_CODE,
    DEFAULT_BEHAVIORS,
)


def load_behavior(code):
    namespace = {
        "self": primitives.self,
        "ball": primitives.ball,
        "teammates": primitives.teammates,
        "starting_position": primitives.starting_position,
        "own_goal": primitives.own_goal,
        "opponent_goal": primitives.opponent_goal,
        "control_range": primitives.control_range,
        "can_kick": primitives.can_kick,
        "distance": primitives.distance,
        "direction_to": primitives.direction_to,
        "speed_for_distance": primitives.speed_for_distance,
        "kick_force_for_distance": primitives.kick_force_for_distance,
        "move": primitives.move,
        "kick": primitives.kick,
        "wait": primitives.wait,
    }

    exec(code, namespace)

    return namespace


def execute_behavior(code, context):
    namespace = load_behavior(code)

    set_current_context(context)

    try:
        action = namespace["play"]()
    finally:
        clear_current_context()

    return action, namespace


def test_attacker_moves_to_attacking_position_when_ball_is_in_own_half(context):
    context.player = (1, (18.0, 5.0))
    context.ball = ((10.0, 10.0), (0.0, 0.0))
    context.starting_position = (16.0, 5.0)
    context.side = Side.LEFT

    action, _ = execute_behavior(
        ATTACKER_CODE,
        context,
    )

    assert isinstance(action, MoveAction)


def test_attacker_moves_towards_ball_when_ball_is_in_opponent_half(context):
    context.player = (1, (25.0, 10.0))
    context.ball = ((32.0, 10.0), (0.0, 0.0))
    context.side = Side.LEFT

    action, _ = execute_behavior(
        ATTACKER_CODE,
        context,
    )

    assert isinstance(action, MoveAction)

    expected_direction = primitives.direction_to(
        (25.0, 10.0),
        (32.0, 10.0),
    )

    assert action.move_direction == expected_direction


def test_attacker_kicks_towards_opponent_goal(context):
    context.player = (1, (32.0, 10.0))
    context.ball = ((32.5, 10.0), (0.0, 0.0))
    context.side = Side.LEFT
    context.control_range = 1.0
    context.tics_until_kick = 0

    action, _ = execute_behavior(
        ATTACKER_CODE,
        context,
    )

    assert isinstance(action, KickAction)

    expected_direction = primitives.direction_to(
        (32.5, 10.0),
        RIGHT_GOAL,
    )

    assert action.kick_direction == expected_direction


def test_attacker_kicks_towards_left_goal_when_on_right_side(context):
    context.player = (1, (8.0, 10.0))
    context.ball = ((7.5, 10.0), (0.0, 0.0))
    context.side = Side.RIGHT
    context.control_range = 1.0
    context.tics_until_kick = 0

    action, _ = execute_behavior(
        ATTACKER_CODE,
        context,
    )

    expected_direction = primitives.direction_to(
        context.ball[0],
        LEFT_GOAL,
    )

    assert isinstance(action, KickAction)
    assert action.kick_direction == expected_direction


def test_attacker_attacking_position_is_relative_to_side(context):
    context.starting_position = (24.0, 5.0)
    context.side = Side.RIGHT

    _, namespace = execute_behavior(
        ATTACKER_CODE,
        context,
    )

    set_current_context(context)

    try:
        position = namespace["attacking_position"]()
    finally:
        clear_current_context()

    assert position == (10.0, 5.0)


def test_attacker_waits_when_already_at_attacking_position(context):
    context.player = (1, (30.0, 5.0))
    context.ball = ((10.0, 10.0), (0.0, 0.0))
    context.starting_position = (16.0, 5.0)
    context.side = Side.LEFT

    action, _ = execute_behavior(
        ATTACKER_CODE,
        context,
    )

    assert isinstance(action, WaitAction)


def test_defender_moves_to_defensive_position_when_ball_is_in_opponent_half(
    context,
):
    context.player = (1, (20.0, 5.0))
    context.ball = ((30.0, 10.0), (0.0, 0.0))
    context.starting_position = (8.0, 5.0)
    context.side = Side.LEFT

    action, _ = execute_behavior(
        DEFENDER_CODE,
        context,
    )

    assert isinstance(action, MoveAction)

    expected_direction = primitives.direction_to(
        context.player[1],
        (10.0, 5.0),
    )

    assert action.move_direction == expected_direction


def test_defender_moves_towards_ball_when_ball_is_in_own_half(
    context,
):
    context.player = (1, (10.0, 10.0))
    context.ball = ((5.0, 10.0), (0.0, 0.0))
    context.side = Side.LEFT

    action, _ = execute_behavior(
        DEFENDER_CODE,
        context,
    )

    assert isinstance(action, MoveAction)

    expected_direction = primitives.direction_to(
        context.player[1],
        context.ball[0],
    )

    assert action.move_direction == expected_direction


def test_defender_passes_to_closest_teammate(context):
    context.player = (1, (5.0, 10.0))
    context.ball = ((5.5, 10.0), (0.0, 0.0))
    context.teammates = [
        (2, (8.0, 10.0)),
        (3, (15.0, 10.0)),
    ]
    context.side = Side.LEFT
    context.control_range = 1.0
    context.tics_until_kick = 0

    action, _ = execute_behavior(
        DEFENDER_CODE,
        context,
    )

    assert isinstance(action, KickAction)

    closest_teammate_position = context.teammates[0][1]

    expected_direction = primitives.direction_to(
        context.ball[0],
        closest_teammate_position,
    )

    assert action.kick_direction == expected_direction


def test_defender_waits_when_ball_is_controlled_but_cannot_kick(
    context,
):
    context.player = (1, (5.0, 10.0))
    context.ball = ((5.5, 10.0), (0.0, 0.0))
    context.side = Side.LEFT
    context.control_range = 1.0
    context.tics_until_kick = 2

    action, _ = execute_behavior(
        DEFENDER_CODE,
        context,
    )

    assert isinstance(action, WaitAction)


def test_defender_defensive_position_is_relative_to_side(context):
    context.player = (1, (20.0, 5.0))
    context.ball = ((10.0, 10.0), (0.0, 0.0))
    context.starting_position = (32.0, 5.0)
    context.side = Side.RIGHT

    action, _ = execute_behavior(
        DEFENDER_CODE,
        context,
    )

    assert isinstance(action, MoveAction)

    expected_direction = primitives.direction_to(
        context.player[1],
        (30.0, 5.0),
    )

    assert action.move_direction == expected_direction


def test_midfielder_moves_towards_ball(context):
    context.player = (1, (20.0, 5.0))
    context.ball = ((30.0, 15.0), (0.0, 0.0))
    context.control_range = 1.0

    action, _ = execute_behavior(
        MIDFIELDER_CODE,
        context,
    )

    assert isinstance(action, MoveAction)

    expected_direction = primitives.direction_to(
        context.player[1],
        context.ball[0],
    )

    assert action.move_direction == expected_direction


def test_midfielder_passes_to_closest_teammate(context):
    context.player = (1, (20.0, 10.0))
    context.ball = ((20.5, 10.0), (0.0, 0.0))
    context.teammates = [
        (2, (22.0, 10.0)),
        (3, (30.0, 10.0)),
    ]
    context.control_range = 1.0
    context.tics_until_kick = 0

    action, _ = execute_behavior(
        MIDFIELDER_CODE,
        context,
    )

    assert isinstance(action, KickAction)

    closest_teammate_position = context.teammates[0][1]

    expected_direction = primitives.direction_to(
        context.ball[0],
        closest_teammate_position,
    )

    assert action.kick_direction == expected_direction


def test_midfielder_waits_when_ball_is_controlled_but_cannot_kick(
    context,
):
    context.player = (1, (20.0, 10.0))
    context.ball = ((20.5, 10.0), (0.0, 0.0))
    context.control_range = 1.0
    context.tics_until_kick = 3

    action, _ = execute_behavior(
        MIDFIELDER_CODE,
        context,
    )

    assert isinstance(action, WaitAction)


def test_midfielder_chooses_first_teammate_when_distances_are_equal(
    context,
):
    context.player = (1, (20.0, 10.0))
    context.ball = ((20.0, 10.0), (0.0, 0.0))
    context.teammates = [
        (2, (22.0, 10.0)),
        (3, (18.0, 10.0)),
    ]
    context.control_range = 1.0
    context.tics_until_kick = 0

    action, _ = execute_behavior(
        MIDFIELDER_CODE,
        context,
    )

    expected_direction = primitives.direction_to(
        context.ball[0],
        context.teammates[0][1],
    )

    assert isinstance(action, KickAction)
    assert action.kick_direction == expected_direction


def test_ball_at_midfield_is_defender_half_not_attacker_half(context):
    context.ball = ((20.0, 10.0), (0.0, 0.0))
    context.side = Side.LEFT

    _, attacker_namespace = execute_behavior(
        ATTACKER_CODE,
        context,
    )

    _, defender_namespace = execute_behavior(
        DEFENDER_CODE,
        context,
    )

    set_current_context(context)
    try:
        assert not attacker_namespace["is_ball_in_opponent_half"](
            context.ball[0]
        )
        assert defender_namespace["is_ball_in_own_half"](
            context.ball[0]
        )
    finally:
        clear_current_context()