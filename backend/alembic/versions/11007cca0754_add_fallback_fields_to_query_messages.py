"""add_fallback_fields_to_query_messages

Revision ID: 11007cca0754
Revises: 541581bddab3
Create Date: 2026-07-13 21:45:14.801703

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "11007cca0754"
down_revision: Union[str, Sequence[str], None] = "541581bddab3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "query_messages",
        sa.Column("was_fallback", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "query_messages",
        sa.Column("fallback_model_name", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("query_messages", "fallback_model_name")
    op.drop_column("query_messages", "was_fallback")
