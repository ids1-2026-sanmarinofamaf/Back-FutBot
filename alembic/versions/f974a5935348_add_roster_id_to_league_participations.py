"""add roster_id to league_participations

Revision ID: f974a5935348
Revises: d5c2c1de9603
Create Date: 2026-10-15 19:19:02.201017

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f974a5935348'
down_revision: Union[str, Sequence[str], None] = 'd5c2c1de9603'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    with op.batch_alter_table(
        'league_participations',
        schema=None
    ) as batch_op:

        batch_op.add_column(
            sa.Column(
                'roster_id',
                sa.Integer(),
                nullable=False
            )
        )

        batch_op.create_foreign_key(
            'fk_league_participation_roster',
            'rosters',
            ['roster_id'],
            ['id']
        )


def downgrade() -> None:
    with op.batch_alter_table(
        'league_participations',
        schema=None
    ) as batch_op:

        batch_op.drop_constraint(
            'fk_league_participation_roster',
            type_='foreignkey'
        )

        batch_op.drop_column('roster_id')
