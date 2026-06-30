"""add_evaluation_completed_to_notificationtype

Revision ID: 7620b9baf174
Revises: 184d43e75538
Create Date: 2026-06-26 13:31:14.562979

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7620b9baf174"
down_revision: Union[str, Sequence[str], None] = "184d43e75538"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'evaluation_completed'"
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres doesn't easily support dropping an enum value, so we leave it as a no-op
    pass
