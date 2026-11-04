"""merge league fixture and club statistics migrations

Revision ID: df5dd24609fc
Revises: 718e30488bcc, fd7fd4c36d3b
Create Date: 2026-10-31 01:19:52.685154

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df5dd24609fc'
down_revision: Union[str, Sequence[str], None] = ('718e30488bcc', 'fd7fd4c36d3b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
