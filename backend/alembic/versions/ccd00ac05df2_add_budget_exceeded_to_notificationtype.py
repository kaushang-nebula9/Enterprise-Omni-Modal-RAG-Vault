"""add_budget_exceeded_to_notificationtype

Revision ID: ccd00ac05df2
Revises: 3cc0e8f53081
Create Date: 2026-06-26 15:13:28.724114

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "ccd00ac05df2"
down_revision: Union[str, Sequence[str], None] = "3cc0e8f53081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'budget_exceeded'"
        )


def downgrade() -> None:
    """Downgrade schema."""
    pass
