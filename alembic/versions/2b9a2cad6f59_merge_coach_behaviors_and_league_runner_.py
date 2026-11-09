"""merge coach behaviors and league runner migrations

Revision ID: 2b9a2cad6f59
Revises: b36f85498abb, ee4b307fde78
Create Date: 2026-11-05 00:44:52.328619

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b9a2cad6f59'
down_revision: Union[str, Sequence[str], None] = ('b36f85498abb', 'ee4b307fde78')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
