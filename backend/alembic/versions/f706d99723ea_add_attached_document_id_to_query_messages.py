"""add attached_document_id to query_messages

Revision ID: f706d99723ea
Revises: 989a9aa151dd
Create Date: 2026-06-19 17:48:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f706d99723ea"
down_revision: Union[str, Sequence[str], None] = "989a9aa151dd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "query_messages", sa.Column("attached_document_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_query_messages_attached_document_id",
        "query_messages",
        "documents",
        ["attached_document_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_query_messages_attached_document_id", "query_messages", type_="foreignkey"
    )
    op.drop_column("query_messages", "attached_document_id")
