"""add league runner persistence fields

Revision ID: ee4b307fde78
Revises: df5dd24609fc
Create Date: 2026-11-02 16:01:07.327527

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee4b307fde78'
down_revision: Union[str, Sequence[str], None] = 'df5dd24609fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('leagues', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'last_completed_round',
                sa.Integer(),
                server_default='0',
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                'break_ends_at',
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.create_check_constraint(
            'ck_league_last_completed_round_non_negative',
            'last_completed_round >= 0',
        )

    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('home_goals', sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column('away_goals', sa.Integer(), nullable=True)
        )

        batch_op.create_check_constraint(
            'ck_match_home_goals_non_negative',
            'home_goals IS NULL OR home_goals >= 0',
        )

        batch_op.create_check_constraint(
            'ck_match_away_goals_non_negative',
            'away_goals IS NULL OR away_goals >= 0',
        )

        batch_op.create_check_constraint(
            'ck_league_match_score_matches_state',
            "league_id IS NULL OR ("
            "(state = 'FINALIZADO' "
            "AND home_goals IS NOT NULL "
            "AND away_goals IS NOT NULL) "
            "OR "
            "(state <> 'FINALIZADO' "
            "AND home_goals IS NULL "
            "AND away_goals IS NULL)"
            ")",
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.drop_constraint(
            'ck_league_match_score_matches_state',
            type_='check',
        )
        batch_op.drop_constraint(
            'ck_match_away_goals_non_negative',
            type_='check',
        )
        batch_op.drop_constraint(
            'ck_match_home_goals_non_negative',
            type_='check',
        )

        batch_op.drop_column('away_goals')
        batch_op.drop_column('home_goals')

    with op.batch_alter_table('leagues', schema=None) as batch_op:
        batch_op.drop_constraint(
            'ck_league_last_completed_round_non_negative',
            type_='check',
        )

        batch_op.drop_column('break_ends_at')
        batch_op.drop_column('last_completed_round')
