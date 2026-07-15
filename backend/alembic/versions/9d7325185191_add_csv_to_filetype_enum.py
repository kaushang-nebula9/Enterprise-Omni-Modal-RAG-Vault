"""add csv to filetype enum

Revision ID: 9d7325185191
Revises: c9e076881727
Create Date: 2026-07-15 17:50:16.019065

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9d7325185191"
down_revision: Union[str, Sequence[str], None] = "c9e076881727"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE filetype ADD VALUE 'csv'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
