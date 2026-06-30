"""add status, file_path, excel_schema to documents

Revision ID: 4bd6768dcde2
Revises: e6eb9cfe9778
Create Date: 2026-06-15 12:45:30.041630

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4bd6768dcde2"
down_revision: Union[str, Sequence[str], None] = "e6eb9cfe9778"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

document_status_enum = sa.Enum(
    "pending", "processing", "ready", "failed", name="documentstatus"
)


def upgrade() -> None:
    """Upgrade schema."""
    # Create the enum type first, then add columns
    document_status_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "documents",
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "ready", "failed", name="documentstatus"),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column("documents", sa.Column("file_path", sa.String(), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "excel_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("documents", "excel_schema")
    op.drop_column("documents", "file_path")
    op.drop_column("documents", "status")
    document_status_enum.drop(op.get_bind(), checkfirst=True)
