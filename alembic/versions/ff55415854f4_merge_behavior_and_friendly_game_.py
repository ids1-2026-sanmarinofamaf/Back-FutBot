"""merge behavior and friendly game migrations

Revision ID: ff55415854f4
Revises: 017bba20c37f, 98c6ee7ce9cf
Create Date: 2026-10-04 13:19:56.690444

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff55415854f4'
down_revision: Union[str, Sequence[str], None] = ('017bba20c37f', '98c6ee7ce9cf')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
