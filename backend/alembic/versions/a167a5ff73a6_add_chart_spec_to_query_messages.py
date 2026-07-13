"""add_chart_spec_to_query_messages

Revision ID: a167a5ff73a6
Revises: b3b4c5d6e7f8
Create Date: 2026-07-13 11:55:56.922515

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a167a5ff73a6"
down_revision: Union[str, Sequence[str], None] = "b3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "query_messages",
        sa.Column("chart_spec", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("query_messages", "chart_spec")
