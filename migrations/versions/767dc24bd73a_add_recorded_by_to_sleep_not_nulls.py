"""add_recorded_by_to_sleep_not_nulls

Revision ID: 767dc24bd73a
Revises: 6e61a5de49e4
Create Date: 2025-05-14 07:22:20.281311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '767dc24bd73a'
down_revision: Union[str, None] = '6e61a5de49e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('sleep', 'recorded_by',
               existing_type=sa.INTEGER(),
               nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('sleep', 'recorded_by',
               existing_type=sa.INTEGER(),
               nullable=True)
    # ### end Alembic commands ###
