"""refactor_model_management_providers

Revision ID: f28cffd86205
Revises: a167a5ff73a6
Create Date: 2026-07-13 14:23:15.925801

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f28cffd86205"
down_revision: Union[str, Sequence[str], None] = "a167a5ff73a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "available_models",
        sa.Column("provider_id", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "available_models", sa.Column("base_url", sa.String(length=500), nullable=True)
    )
    op.add_column(
        "available_models",
        sa.Column(
            "input_cost_per_million_tokens",
            sa.Numeric(precision=10, scale=4),
            nullable=True,
        ),
    )
    op.add_column(
        "available_models",
        sa.Column(
            "output_cost_per_million_tokens",
            sa.Numeric(precision=10, scale=4),
            nullable=True,
        ),
    )
    op.add_column(
        "available_models",
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "available_models",
        sa.Column("api_key", sa.String(length=500), nullable=True, server_default=""),
    )
    op.add_column(
        "available_models",
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "available_models",
        sa.Column("model_name", sa.String(length=255), nullable=True),
    )

    # Make old columns nullable
    op.alter_column(
        "available_models",
        "provider",
        existing_type=sa.Enum("anthropic", "openrouter", name="modelprovider"),
        nullable=True,
    )
    op.alter_column(
        "available_models", "model_string", existing_type=sa.String(), nullable=True
    )

    # Data Backfill
    op.execute(
        "UPDATE available_models SET provider_id = 'anthropic' WHERE provider = 'anthropic'"
    )
    op.execute(
        "UPDATE available_models SET provider_id = 'openrouter', base_url = 'https://openrouter.ai/api/v1' WHERE provider = 'openrouter'"
    )
    op.execute(
        "UPDATE available_models SET provider_id = 'openai_compat' WHERE provider IS NOT NULL AND provider NOT IN ('anthropic', 'openrouter')"
    )
    op.execute(
        "UPDATE available_models SET provider_id = 'openai_compat' WHERE provider_id IS NULL"
    )

    op.execute(
        "UPDATE available_models SET model_name = model_string WHERE model_string IS NOT NULL"
    )
    op.execute(
        "UPDATE available_models SET input_cost_per_million_tokens = input_price_per_million WHERE input_price_per_million IS NOT NULL"
    )
    op.execute(
        "UPDATE available_models SET output_cost_per_million_tokens = output_price_per_million WHERE output_price_per_million IS NOT NULL"
    )
    op.execute("UPDATE available_models SET api_key = '', is_default = false")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "available_models", "model_string", existing_type=sa.String(), nullable=False
    )
    op.alter_column(
        "available_models",
        "provider",
        existing_type=sa.Enum("anthropic", "openrouter", name="modelprovider"),
        nullable=False,
    )

    op.drop_column("available_models", "model_name")
    op.drop_column("available_models", "is_default")
    op.drop_column("available_models", "api_key")
    op.drop_column("available_models", "tenant_id")
    op.drop_column("available_models", "output_cost_per_million_tokens")
    op.drop_column("available_models", "input_cost_per_million_tokens")
    op.drop_column("available_models", "base_url")
    op.drop_column("available_models", "provider_id")
