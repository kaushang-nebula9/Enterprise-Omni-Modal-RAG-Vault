"""add sql and results to query_messages

Revision ID: f706d99723eb
Revises: 047d72ea7b8c
Create Date: 2026-07-08 10:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f706d99723eb"
down_revision: Union[str, Sequence[str], None] = "047d72ea7b8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "query_messages",
        sa.Column("generated_sql", sa.Text(), nullable=True),
    )
    op.add_column(
        "query_messages",
        sa.Column("query_results", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("query_messages", "query_results")
    op.drop_column("query_messages", "generated_sql")
