ATTACKER_NAME = "Attacker"

ATTACKER_CODE = """
def is_ball_in_opponent_half(ball_position):
    return (
        distance(ball_position, opponent_goal())
        < distance(ball_position, own_goal())
    )


def attacking_position():
    own = own_goal()
    opponent = opponent_goal()
    _, start_y = starting_position()

    return (
        own[0] + (opponent[0] - own[0]) * 0.75,
        start_y,
    )


def move_to(my_position, target):
    target_distance = distance(my_position, target)

    if target_distance == 0:
        return wait()

    return move(
        direction_to(my_position, target),
        speed_for_distance(target_distance),
    )


def play():
    _, my_position = self()
    ball_position, _ = ball()

    if not is_ball_in_opponent_half(ball_position):
        return move_to(
            my_position,
            attacking_position(),
        )

    ball_distance = distance(
        my_position,
        ball_position,
    )

    if ball_distance <= control_range():
        if not can_kick():
            return wait()

        goal = opponent_goal()

        goal_direction = direction_to(
            ball_position,
            goal,
        )

        goal_distance = distance(
            ball_position,
            goal,
        )

        return kick(
            goal_direction,
            kick_force_for_distance(
                goal_direction,
                goal_distance,
            )
        )

    return move_to(
        my_position,
        ball_position,
    )
"""


DEFENDER_NAME = "Defender"

DEFENDER_CODE = """
def is_ball_in_own_half(ball_position):
    return (
        distance(ball_position, own_goal())
        <= distance(ball_position, opponent_goal())
    )


def defensive_position():
    own = own_goal()
    opponent = opponent_goal()
    _, start_y = starting_position()

    return (
        own[0] + (opponent[0] - own[0]) * 0.25,
        start_y,
    )


def most_advanced_teammate():
    goal = opponent_goal()

    best_position = None
    best_distance = None

    for _, teammate_position in teammates():
        teammate_goal_distance = distance(
            teammate_position,
            goal,
        )

        if (
            best_distance is None
            or teammate_goal_distance < best_distance
        ):
            best_position = teammate_position
            best_distance = teammate_goal_distance

    return best_position


def move_to(my_position, target):
    target_distance = distance(my_position, target)

    if target_distance == 0:
        return wait()

    return move(
        direction_to(my_position, target),
        speed_for_distance(target_distance),
    )


def play():
    _, my_position = self()
    ball_position, _ = ball()

    if not is_ball_in_own_half(ball_position):
        return move_to(
            my_position,
            defensive_position(),
        )

    ball_distance = distance(
        my_position,
        ball_position,
    )

    if ball_distance <= control_range():
        if not can_kick():
            return wait()

        teammate_position = most_advanced_teammate()

        pass_direction = direction_to(
            ball_position,
            teammate_position,
        )

        pass_distance = distance(
            ball_position,
            teammate_position,
        )

        return kick(
            pass_direction,
            kick_force_for_distance(
                pass_direction,
                pass_distance,
            )
        )

    return move_to(
        my_position,
        ball_position,
    )
"""


MIDFIELDER_NAME = "Midfielder"

MIDFIELDER_CODE = """
def most_advanced_teammate():
    goal = opponent_goal()

    best_position = None
    best_distance = None

    for _, teammate_position in teammates():
        teammate_goal_distance = distance(
            teammate_position,
            goal,
        )

        if (
            best_distance is None
            or teammate_goal_distance < best_distance
        ):
            best_position = teammate_position
            best_distance = teammate_goal_distance

    return best_position


def play():
    _, my_position = self()
    ball_position, _ = ball()

    ball_distance = distance(
        my_position,
        ball_position,
    )

    if ball_distance <= control_range():
        if not can_kick():
            return wait()

        teammate_position = most_advanced_teammate()

        pass_direction = direction_to(
            ball_position,
            teammate_position,
        )

        pass_distance = distance(
            ball_position,
            teammate_position,
        )

        return kick(
            pass_direction,
            kick_force_for_distance(
                pass_direction,
                pass_distance,
            )
        )

    return move(
        direction_to(
            my_position,
            ball_position,
        ),
        speed_for_distance(
            ball_distance,
        ),
    )
"""

DEFAULT_BEHAVIORS = (
    {
        "name": ATTACKER_NAME,
        "code": ATTACKER_CODE,
    },
    {
        "name": MIDFIELDER_NAME,
        "code": MIDFIELDER_CODE,
    },
    {
        "name": DEFENDER_NAME,
        "code": DEFENDER_CODE,
    },
)