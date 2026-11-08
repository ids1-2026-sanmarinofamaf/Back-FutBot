"""agregar fecha a los partidos

Revision ID: 718e30488bcc
Revises: fe788b9cf5b5
Create Date: 2026-10-28 22:30:19.820672

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '718e30488bcc'
down_revision: Union[str, Sequence[str], None] = 'fe788b9cf5b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('round', sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            'ck_match_round_positive',
            'round IS NULL OR round >= 1',
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.drop_constraint('ck_match_round_positive', type_='check')
        batch_op.drop_column('round')
