"""support global default behaviors

Revision ID: 7812d1c35ff8
Revises: 62d4633c8641
Create Date: 2026-10-04 01:05:26.437555

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7812d1c35ff8'
down_revision: Union[str, Sequence[str], None] = '62d4633c8641'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("behaviors") as batch_op:

        batch_op.alter_column(
            "club_id",
            existing_type=sa.Integer(),
            nullable=True,
        )

        batch_op.add_column(
            sa.Column(
                "is_default",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

        batch_op.create_check_constraint(
            "ck_behavior_default_scope",
            "(is_default = TRUE AND club_id IS NULL) "
            "OR (is_default = FALSE AND club_id IS NOT NULL)",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("behaviors") as batch_op:
        batch_op.drop_constraint(
            "ck_behavior_default_scope",
            type_="check",
        )

        batch_op.drop_column("is_default")

        batch_op.alter_column(
            "club_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
