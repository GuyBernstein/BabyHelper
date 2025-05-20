"""add co-parent relationship_type

Revision ID: 2a8f100f05d5
Revises: f12573cff809
Create Date: 2025-05-08 07:32:30.211751

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2a8f100f05d5'
down_revision: Union[str, None] = 'f12573cff809'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the Enum type first
    relationshiptype = postgresql.ENUM('PARTNER', 'GRANDPARENT', 'NANNY', 'OTHER', name='relationshiptype')
    relationshiptype.create(op.get_bind())

    # Then add the columns using the enum type
    op.add_column('baby_coparent', sa.Column('relationship_type', sa.Enum('PARTNER', 'GRANDPARENT', 'NANNY', 'OTHER', name='relationshiptype'), nullable=False))
    op.add_column('coparent_invitation', sa.Column('relationship_type', sa.Enum('PARTNER', 'GRANDPARENT', 'NANNY', 'OTHER', name='relationshiptype'), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    # First drop the columns
    op.drop_column('coparent_invitation', 'relationship_type')
    op.drop_column('baby_coparent', 'relationship_type')

    # Then drop the enum type
    relationshiptype = postgresql.ENUM('PARTNER', 'GRANDPARENT', 'NANNY', 'OTHER', name='relationshiptype')
    relationshiptype.drop(op.get_bind())