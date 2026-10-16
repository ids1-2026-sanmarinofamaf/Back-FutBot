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
)


def load_behavior(code):
    namespace = {
        "self": primitives.self,
        "ball": primitives.ball,
        "teammates": primitives.teammates,
        "opponents": primitives.opponents,
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
    assert action.kick_force_factor == 1.0


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
    assert action.kick_force_factor == 1.0


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


def test_attacker_unmarks_when_ball_is_outside_zone(context):
    context.player = (1, (25.0, 10.0))
    context.ball = ((10.0, 10.0), (0.0, 0.0))
    context.starting_position = (30.0, 10.0)
    context.side = Side.LEFT
    context.opponents = [
        (7, (30.0, 7.0)),
        (8, (25.0, 10.0)),
        (9, (20.0, 10.0)),
    ]

    action, namespace = execute_behavior(
        ATTACKER_CODE,
        context,
    )

    set_current_context(context)
    try:
        target = namespace["unmarked_position"]()
    finally:
        clear_current_context()

    assert isinstance(action, MoveAction)

    expected_direction = primitives.direction_to(
        context.player[1],
        target,
    )

    assert action.move_direction == expected_direction


def test_attacker_unmarks_away_from_opponents(context):
    context.starting_position = (30.0, 10.0)
    context.side = Side.LEFT
    context.opponents = [
        (7, (30.0, 7.0)),
        (8, (30.0, 6.0)),
        (9, (25.0, 10.0)),
    ]

    _, namespace = execute_behavior(
        ATTACKER_CODE,
        context,
    )

    set_current_context(context)
    try:
        target = namespace["unmarked_position"]()
    finally:
        clear_current_context()

    assert target == (30.0, 13.0)


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


def test_defender_passes_to_most_advanced_teammate(context):
    context.player = (1, (5.0, 10.0))
    context.ball = ((5.5, 10.0), (0.0, 0.0))
    context.teammates = [
        (2, (8.0, 10.0)),   # más cercano
        (3, (15.0, 10.0)),  # más avanzado
    ]

    context.side = Side.LEFT
    context.control_range = 1.0
    context.tics_until_kick = 0

    action, _ = execute_behavior(
        DEFENDER_CODE,
        context,
    )

    assert isinstance(action, KickAction)

    most_advanced_position = context.teammates[1][1]

    expected_direction = primitives.direction_to(
        context.ball[0],
        most_advanced_position,
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


def test_defender_marks_opponent_in_defensive_zone_when_ball_is_outside(
    context,
):
    context.player = (1, (10.0, 10.0))
    context.ball = ((30.0, 10.0), (0.0, 0.0))
    context.side = Side.LEFT
    context.opponents = [
        (7, (5.0, 10.0)),
        (8, (15.0, 10.0)),
        (9, (30.0, 10.0)),
    ]

    action, namespace = execute_behavior(
        DEFENDER_CODE,
        context,
    )

    set_current_context(context)
    try:
        expected_target = namespace["marking_position"](
            (5.0, 10.0)
        )
    finally:
        clear_current_context()

    assert isinstance(action, MoveAction)

    expected_direction = primitives.direction_to(
        context.player[1],
        expected_target,
    )

    assert action.move_direction == expected_direction


def test_defender_marks_opponent_closest_to_own_goal(context):
    context.side = Side.LEFT
    context.opponents = [
        (7, (12.0, 10.0)),
        (8, (5.0, 10.0)),
        (9, (30.0, 10.0)),
    ]

    _, namespace = execute_behavior(
        DEFENDER_CODE,
        context,
    )

    set_current_context(context)
    try:
        opponent = namespace["opponent_to_mark"]()
    finally:
        clear_current_context()

    assert opponent == (5.0, 10.0)


def test_defender_stays_in_zone_when_ball_is_outside_and_no_opponent_to_mark(
    context,
):
    context.player = (1, (10.0, 5.0))
    context.ball = ((30.0, 15.0), (0.0, 0.0))
    context.starting_position = (8.0, 5.0)
    context.side = Side.LEFT
    context.opponents = [
        (7, (20.0, 10.0)),
        (8, (25.0, 10.0)),
        (9, (30.0, 10.0)),
    ]

    action, _ = execute_behavior(
        DEFENDER_CODE,
        context,
    )

    assert isinstance(action, MoveAction)

    expected_direction = primitives.direction_to(
        context.player[1],
        (16.0, 5.0),
    )

    assert action.move_direction == expected_direction


def test_midfielder_stays_in_zone_when_ball_is_outside(context):
    context.player = (1, (20.0, 5.0))
    context.ball = ((30.0, 15.0), (0.0, 0.0))
    context.starting_position = (20.0, 10.0)
    context.side = Side.LEFT
    context.control_range = 1.0

    action, _ = execute_behavior(
        MIDFIELDER_CODE,
        context,
    )

    assert isinstance(action, MoveAction)

    expected_direction = primitives.direction_to(
        context.player[1],
        (28.0, 10.0),
    )

    assert action.move_direction == expected_direction


def test_midfielder_passes_to_closest_teammate(context):
    context.player = (1, (20.0, 10.0))
    context.ball = ((20.5, 10.0), (0.0, 0.0))
    context.teammates = [
        (2, (22.0, 10.0)),
        (3, (30.0, 10.0)),
    ]
    context.side = Side.LEFT
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


def test_midfielder_moves_towards_ball_when_ball_is_inside_zone(context):
    context.player = (1, (15.0, 5.0))
    context.ball = ((20.0, 10.0), (0.0, 0.0))
    context.side = Side.LEFT
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


def test_role_zones_include_expected_positions(context):
    context.side = Side.LEFT

    _, attacker = execute_behavior(ATTACKER_CODE, context)
    _, midfielder = execute_behavior(MIDFIELDER_CODE, context)
    _, defender = execute_behavior(DEFENDER_CODE, context)

    set_current_context(context)
    try:
        assert defender["ball_in_zone"]((10.0, 10.0))
        assert midfielder["ball_in_zone"]((20.0, 10.0))
        assert attacker["ball_in_zone"]((30.0, 10.0))

        assert not defender["ball_in_zone"]((30.0, 10.0))
        assert not attacker["ball_in_zone"]((10.0, 10.0))
    finally:
        clear_current_context()