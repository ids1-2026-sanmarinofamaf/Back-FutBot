"""update default behaviors

Revision ID: 399c37f71aee
Revises: c3f83b002c8e
Create Date: 2026-10-05

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "399c37f71aee"
down_revision: Union[str, Sequence[str], None] = "c3f83b002c8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ------------------------------------------------------------------
# NEW BEHAVIORS
# ------------------------------------------------------------------

NEW_DEFENDER_CODE = """
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


def clearance_target():
    own = own_goal()
    opponent = opponent_goal()

    return (
        own[0] + (opponent[0] - own[0]) * 0.5,
        own[1],
    )


def teammate_near_ball(ball_position, my_ball_distance):
    for _, teammate_position in teammates():
        teammate_distance = distance(
            teammate_position,
            ball_position,
        )

        if (
            teammate_distance <= 2.0
            and teammate_distance < my_ball_distance
        ):
            return True

    return False


def move_to(my_position, target):
    target_distance = distance(
        my_position,
        target,
    )

    if target_distance == 0:
        return wait()

    return move(
        direction_to(
            my_position,
            target,
        ),
        speed_for_distance(
            target_distance,
        ),
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

    if ball_distance > control_range():

        if teammate_near_ball(
            ball_position,
            ball_distance,
        ):
            return move_to(
                my_position,
                defensive_position(),
            )

        return move_to(
            my_position,
            ball_position,
        )

    if not can_kick():
        return wait()

    target = clearance_target()

    clear_direction = direction_to(
        ball_position,
        target,
    )

    clear_distance = distance(
        ball_position,
        target,
    )

    return kick(
        clear_direction,
        kick_force_for_distance(
            clear_direction,
            clear_distance,
        ),
    )
"""


NEW_MIDFIELDER_CODE = """
def best_teammate_to_pass():
    goal = opponent_goal()

    best_position = None
    best_goal_distance = None

    for _, teammate_position in teammates():
        teammate_goal_distance = distance(
            teammate_position,
            goal,
        )

        if (
            best_goal_distance is None
            or teammate_goal_distance < best_goal_distance
        ):
            best_position = teammate_position
            best_goal_distance = teammate_goal_distance

    return best_position


def teammate_near_ball(ball_position, my_ball_distance):
    for _, teammate_position in teammates():
        teammate_distance = distance(
            teammate_position,
            ball_position,
        )

        if (
            teammate_distance <= 2.0
            and teammate_distance < my_ball_distance
        ):
            return True

    return False


def play():
    _, my_position = self()
    ball_position, _ = ball()

    ball_distance = distance(
        my_position,
        ball_position,
    )

    if ball_distance > control_range():

        if teammate_near_ball(
            ball_position,
            ball_distance,
        ):
            return wait()

        return move(
            direction_to(
                my_position,
                ball_position,
            ),
            speed_for_distance(
                ball_distance,
            ),
        )

    if not can_kick():
        return wait()

    teammate_position = best_teammate_to_pass()

    pass_direction = direction_to(
        ball_position,
        teammate_position,
    )

    return kick(
        pass_direction,
        0.5,
    )
"""


NEW_ATTACKER_CODE = """
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


def teammate_near_ball(ball_position, my_ball_distance):
    for _, teammate_position in teammates():
        teammate_distance = distance(
            teammate_position,
            ball_position,
        )

        if (
            teammate_distance <= 2.0
            and teammate_distance < my_ball_distance
        ):
            return True

    return False


def move_to(my_position, target):
    target_distance = distance(
        my_position,
        target,
    )

    if target_distance == 0:
        return wait()

    return move(
        direction_to(
            my_position,
            target,
        ),
        speed_for_distance(
            target_distance,
        ),
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

    if ball_distance > control_range():

        if teammate_near_ball(
            ball_position,
            ball_distance,
        ):
            return move_to(
                my_position,
                attacking_position(),
            )

        return move_to(
            my_position,
            ball_position,
        )

    if not can_kick():
        return wait()

    goal = opponent_goal()

    return kick(
        direction_to(
            ball_position,
            goal,
        ),
        1.0,
    )
"""


# ------------------------------------------------------------------
# OLD BEHAVIORS
# Estado inmediatamente anterior a esta migration.
# ------------------------------------------------------------------

OLD_DEFENDER_CODE = """
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


OLD_MIDFIELDER_CODE = """
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


OLD_ATTACKER_CODE = """
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


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------

def _update_default_behavior(
    name: str,
    code: str,
) -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            UPDATE behaviors
            SET code = :code
            WHERE name = :name
              AND club_id IS NULL
              AND is_default = TRUE
            """
        ),
        {
            "name": name,
            "code": code,
        },
    )


# ------------------------------------------------------------------
# MIGRATION
# ------------------------------------------------------------------

def upgrade() -> None:
    _update_default_behavior(
        "Defender",
        NEW_DEFENDER_CODE,
    )

    _update_default_behavior(
        "Midfielder",
        NEW_MIDFIELDER_CODE,
    )

    _update_default_behavior(
        "Attacker",
        NEW_ATTACKER_CODE,
    )


def downgrade() -> None:
    _update_default_behavior(
        "Defender",
        OLD_DEFENDER_CODE,
    )

    _update_default_behavior(
        "Midfielder",
        OLD_MIDFIELDER_CODE,
    )

    _update_default_behavior(
        "Attacker",
        OLD_ATTACKER_CODE,
    )