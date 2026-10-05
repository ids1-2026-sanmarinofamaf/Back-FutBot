"""SCRUM-86 update default behaviors

Revision ID: c3f83b002c8e
Revises: ff55415854f4
Create Date: 2026-10-04

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3f83b002c8e"
down_revision: Union[str, Sequence[str], None] = "ff55415854f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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


NEW_MIDFIELDER_CODE = """
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


def closest_teammate(ball_position):
    closest_position = None
    closest_distance = None

    for _, teammate_position in teammates():
        teammate_distance = distance(
            ball_position,
            teammate_position,
        )

        if (
            closest_distance is None
            or teammate_distance < closest_distance
        ):
            closest_position = teammate_position
            closest_distance = teammate_distance

    return closest_position, closest_distance


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

        teammate_position, teammate_distance = closest_teammate(
            ball_position
        )

        pass_direction = direction_to(
            ball_position,
            teammate_position,
        )

        return kick(
            pass_direction,
            kick_force_for_distance(
                pass_direction,
                teammate_distance,
            )
        )

    return move_to(
        my_position,
        ball_position,
    )
"""


OLD_MIDFIELDER_CODE = """
def closest_teammate(ball_position):
    closest_position = None
    closest_distance = None

    for _, teammate_position in teammates():
        teammate_distance = distance(
            ball_position,
            teammate_position,
        )

        if (
            closest_distance is None
            or teammate_distance < closest_distance
        ):
            closest_position = teammate_position
            closest_distance = teammate_distance

    return closest_position, closest_distance


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

        teammate_position, teammate_distance = closest_teammate(
            ball_position
        )

        pass_direction = direction_to(
            ball_position,
            teammate_position,
        )

        return kick(
            pass_direction,
            kick_force_for_distance(
                pass_direction,
                teammate_distance,
            )
        )

    return move(
        direction_to(
            my_position,
            ball_position,
        ),
        speed_for_distance(
            ball_distance
        ),
    )
"""


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


def upgrade() -> None:
    _update_default_behavior(
        "Defender",
        NEW_DEFENDER_CODE,
    )

    _update_default_behavior(
        "Midfielder",
        NEW_MIDFIELDER_CODE,
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