"""add_messages_fts_index

Revision ID: 51ab697fb0fe
Revises: 9d7325185192
Create Date: 2026-07-17 15:01:57.688768

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "51ab697fb0fe"
down_revision: Union[str, Sequence[str], None] = "9d7325185192"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "CREATE INDEX idx_messages_fts ON query_messages USING GIN (to_tsvector('english', content));"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS idx_messages_fts;")
