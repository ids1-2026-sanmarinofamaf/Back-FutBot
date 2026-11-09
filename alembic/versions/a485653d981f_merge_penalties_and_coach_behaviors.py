"""merge penalties and coach behaviors

Revision ID: a485653d981f
Revises: 49523cc14102, 2b9a2cad6f59
Create Date: 2026-11-09 02:12:55.882173

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a485653d981f'
down_revision: Union[str, Sequence[str], None] = ('49523cc14102', '2b9a2cad6f59')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
