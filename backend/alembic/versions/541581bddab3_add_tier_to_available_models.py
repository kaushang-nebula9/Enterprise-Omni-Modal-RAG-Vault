"""add_tier_to_available_models

Revision ID: 541581bddab3
Revises: g39d1e7f4a512
Create Date: 2026-07-13 17:37:19.115313

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "541581bddab3"
down_revision: Union[str, Sequence[str], None] = "g39d1e7f4a512"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add column tier as nullable first
    op.add_column(
        "available_models", sa.Column("tier", sa.String(length=20), nullable=True)
    )
    # Backfill existing rows
    op.execute("UPDATE available_models SET tier = 'balanced'")
    # Make it non-nullable and set server default
    op.alter_column(
        "available_models", "tier", nullable=False, server_default="balanced"
    )
    # Add check constraint for allowed values
    op.create_check_constraint(
        "check_available_models_tier",
        "available_models",
        "tier IN ('fast', 'balanced', 'powerful')",
    )

    # Add resolved_model column to query_messages table
    op.add_column(
        "query_messages",
        sa.Column("resolved_model", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("query_messages", "resolved_model")
    op.drop_constraint("check_available_models_tier", "available_models", type_="check")
    op.drop_column("available_models", "tier")
