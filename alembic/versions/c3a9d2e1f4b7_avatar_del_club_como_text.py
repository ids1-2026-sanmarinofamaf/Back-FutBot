"""avatar del club como Text (guarda la imagen en Base64)

Revision ID: c3a9d2e1f4b7
Revises: df940700a5cc
Create Date: 2026-10-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a9d2e1f4b7'
down_revision: Union[str, Sequence[str], None] = 'df940700a5cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('clubs', schema=None) as batch_op:
        batch_op.alter_column('avatar',
               existing_type=sa.String(length=50),
               type_=sa.Text(),
               existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('clubs', schema=None) as batch_op:
        batch_op.alter_column('avatar',
               existing_type=sa.Text(),
               type_=sa.String(length=50),
               existing_nullable=False)
