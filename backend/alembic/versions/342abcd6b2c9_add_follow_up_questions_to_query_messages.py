"""add follow_up_questions to query_messages

Revision ID: 342abcd6b2c9
Revises: 341abcd6b2c8
Create Date: 2026-07-03 16:35:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "342abcd6b2c9"
down_revision: Union[str, Sequence[str], None] = "341abcd6b2c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "query_messages",
        sa.Column("follow_up_questions", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("query_messages", "follow_up_questions")
