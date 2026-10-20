"""add match id sequence

Revision ID: e8b335ca55cb
Revises: 40374f37fd39
Create Date: 2026-10-13 19:31:24.338240

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8b335ca55cb'
down_revision: Union[str, Sequence[str], None] = '40374f37fd39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from alembic import op

# generate new ids since the last max match id
"""add match id sequence

Revision ID: e8b335ca55cb
Revises: 40374f37fd39
Create Date: 2026-10-13 19:31:24.338240

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8b335ca55cb'
down_revision: Union[str, Sequence[str], None] = '40374f37fd39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# generate new ids since the last max match id
def upgrade() -> None:
    connection = op.get_bind()

    if connection.dialect.name != "postgresql":
        return

    op.execute("""
        CREATE SEQUENCE match_id_seq
        START WITH 1
        INCREMENT BY 1
    """)

    op.execute("""
        SELECT setval(
            'match_id_seq',
            GREATEST(
                COALESCE(
                    (SELECT MAX(match_id)
                     FROM friendly_games),
                    0
                ) + 1,
                1
            ),
            false
        )
    """)


def downgrade() -> None:
    connection = op.get_bind()

    if connection.dialect.name != "postgresql":
        return

    op.execute("DROP SEQUENCE match_id_seq")