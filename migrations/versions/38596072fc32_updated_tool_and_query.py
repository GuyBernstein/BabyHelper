""""tool enums"

Revision ID: 977082407d1b
Revises: 530144d9d6d2
Create Date: 2025-05-29 09:51:39.732898

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '977082407d1b'
down_revision: Union[str, None] = '21310f7dcc3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # First, let's check what values exist in the database
    connection = op.get_bind()

    # Create the enum types
    tooltype_enum = sa.Enum('activity_analyzer', 'sleep_pattern_analyzer', 'feeding_tracker',
                           'health_monitor', 'growth_tracker', 'milestone_tracker',
                           'care_metrics_analyzer', 'schedule_assistant', name='tooltype')
    toolstatus_enum = sa.Enum('active', 'inactive', 'maintenance', name='toolstatus')

    # Create the enums in the database
    tooltype_enum.create(connection, checkfirst=True)
    toolstatus_enum.create(connection, checkfirst=True)

    # Clean up data - trim whitespace and ensure lowercase
    op.execute("UPDATE tool SET tool_type = LOWER(TRIM(tool_type))")
    op.execute("UPDATE tool SET status = LOWER(TRIM(status))")

    # Now alter the columns with proper casting
    # We need to use a more explicit casting approach
    op.execute("""
        ALTER TABLE tool 
        ALTER COLUMN tool_type TYPE tooltype 
        USING tool_type::text::tooltype
    """)

    op.execute("""
        ALTER TABLE tool 
        ALTER COLUMN status TYPE toolstatus 
        USING status::text::toolstatus
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Convert back to VARCHAR
    op.execute("ALTER TABLE tool ALTER COLUMN status TYPE VARCHAR(20) USING status::text")
    op.execute("ALTER TABLE tool ALTER COLUMN tool_type TYPE VARCHAR(50) USING tool_type::text")

    # Drop the enum types
    op.execute("DROP TYPE IF EXISTS toolstatus")
    op.execute("DROP TYPE IF EXISTS tooltype")