"""add_database_access_notification_types

Revision ID: a5f3d4b6c7e8
Revises: cf1e01de4274
Create Date: 2026-07-07 11:58:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a5f3d4b6c7e8"
down_revision: Union[str, Sequence[str], None] = "cf1e01de4274"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'database_access_direct'"
        )
        op.execute(
            "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'database_access_inherited_hierarchy'"
        )
        op.execute(
            "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'database_access_inherited_department'"
        )


def downgrade() -> None:
    """Downgrade schema."""
    pass
