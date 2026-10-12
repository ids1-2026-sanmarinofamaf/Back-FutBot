"""add match id to friendly game

Revision ID: 40374f37fd39
Revises: c3a9d2e1f4b7
Create Date: 2026-10-12 23:37:56.636044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '40374f37fd39'
down_revision: Union[str, Sequence[str], None] = 'c3a9d2e1f4b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.add_column(
        "friendly_games",
        sa.Column(
            "match_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_unique_constraint(
        "uq_friendly_games_match_id",
        "friendly_games",
        ["match_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_friendly_games_match_id",
        "friendly_games",
        type_="unique",
    )

    op.drop_column(
        "friendly_games",
        "match_id",
    )
