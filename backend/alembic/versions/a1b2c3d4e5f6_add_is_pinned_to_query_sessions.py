"""add is_pinned to query_sessions

Revision ID: a1b2c3d4e5f6
Revises: f706d99723ea
Create Date: 2026-06-22 12:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f706d99723ea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_pinned boolean column to query_sessions (default False)."""
    op.add_column(
        "query_sessions",
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Remove is_pinned column from query_sessions."""
    op.drop_column("query_sessions", "is_pinned")
