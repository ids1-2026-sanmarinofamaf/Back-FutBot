"""seed default behaviors

Revision ID: 017bba20c37f
Revises: 7812d1c35ff8
Create Date: 2026-10-04 01:43:49.256192

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '017bba20c37f'
down_revision: Union[str, Sequence[str], None] = '7812d1c35ff8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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


MIDFIELDER_NAME = "Midfielder"

MIDFIELDER_CODE = """
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


def upgrade() -> None:
    behaviors = sa.table(
        "behaviors",
        sa.column("name", sa.String),
        sa.column("code", sa.Text),
        sa.column("club_id", sa.Integer),
        sa.column("is_default", sa.Boolean),
    )

    op.bulk_insert(
        behaviors,
        [
            {
                "name": "Attacker",
                "code": ATTACKER_CODE,
                "club_id": None,
                "is_default": True,
            },
            {
                "name": "Midfielder",
                "code": MIDFIELDER_CODE,
                "club_id": None,
                "is_default": True,
            },
            {
                "name": "Defender",
                "code": DEFENDER_CODE,
                "club_id": None,
                "is_default": True,
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM behaviors
            WHERE club_id IS NULL
              AND is_default = TRUE
              AND name IN ('Attacker', 'Midfielder', 'Defender')
            """
        )
    )
