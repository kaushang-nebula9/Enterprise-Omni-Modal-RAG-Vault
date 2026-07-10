"""add_db_connection_id_to_query_sessions

Revision ID: a2b3c4d5e6f7
Revises: 79791adfa8cf
Create Date: 2026-07-10 14:12:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "79791adfa8cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "query_sessions", sa.Column("db_connection_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_query_sessions_db_connection_id",
        "query_sessions",
        "external_database_connections",
        ["db_connection_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_query_sessions_db_connection_id", "query_sessions", type_="foreignkey"
    )
    op.drop_column("query_sessions", "db_connection_id")
