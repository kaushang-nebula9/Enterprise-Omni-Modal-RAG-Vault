"""drop_legacy_available_model_columns

Revision ID: g39d1e7f4a512
Revises: f28cffd86205
Create Date: 2026-07-13 16:52:00.000000

Drops the legacy columns from the available_models table that were superseded
by the provider registry refactor (f28cffd86205):

  - provider          (Enum: modelprovider) → replaced by provider_id (String)
  - model_string      (String)              → replaced by model_name  (String)
  - input_price_per_million  (Numeric)      → replaced by input_cost_per_million_tokens
  - output_price_per_million (Numeric)      → replaced by output_cost_per_million_tokens

Data was already backfilled in f28cffd86205, so this migration is purely
a destructive cleanup of now-redundant columns.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "g39d1e7f4a512"
down_revision: Union[str, Sequence[str], None] = "f28cffd86205"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the legacy columns made redundant by the provider registry refactor."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {
        col["name"] for col in inspector.get_columns("available_models")
    }

    # Drop legacy pricing columns (replaced by input/output_cost_per_million_tokens)
    if "input_price_per_million" in existing_columns:
        op.drop_column("available_models", "input_price_per_million")
    if "output_price_per_million" in existing_columns:
        op.drop_column("available_models", "output_price_per_million")

    # Drop legacy model identifier (replaced by model_name)
    if "model_string" in existing_columns:
        op.drop_column("available_models", "model_string")

    # Drop legacy provider enum column (replaced by provider_id string)
    if "provider" in existing_columns:
        op.drop_column("available_models", "provider")

    # Drop the now-unused modelprovider enum type (PostgreSQL-specific)
    op.execute("DROP TYPE IF EXISTS modelprovider")


def downgrade() -> None:
    """Restore the legacy columns and re-populate from the new columns."""
    # Re-create the enum type
    modelprovider = sa.Enum("anthropic", "openrouter", name="modelprovider")
    modelprovider.create(op.get_bind(), checkfirst=True)

    # Re-add legacy pricing columns
    op.add_column(
        "available_models",
        sa.Column(
            "input_price_per_million", sa.Numeric(precision=10, scale=4), nullable=True
        ),
    )
    op.add_column(
        "available_models",
        sa.Column(
            "output_price_per_million", sa.Numeric(precision=10, scale=4), nullable=True
        ),
    )

    # Re-add legacy model_string column
    op.add_column(
        "available_models",
        sa.Column("model_string", sa.String(), nullable=True),
    )

    # Re-add legacy provider enum column
    op.add_column(
        "available_models",
        sa.Column(
            "provider",
            sa.Enum("anthropic", "openrouter", name="modelprovider"),
            nullable=True,
        ),
    )

    # Restore data from the new columns
    op.execute(
        "UPDATE available_models "
        "SET model_string = model_name, "
        "    input_price_per_million = input_cost_per_million_tokens, "
        "    output_price_per_million = output_cost_per_million_tokens"
    )
    op.execute(
        "UPDATE available_models "
        "SET provider = 'anthropic'::modelprovider "
        "WHERE provider_id = 'anthropic'"
    )
    op.execute(
        "UPDATE available_models "
        "SET provider = 'openrouter'::modelprovider "
        "WHERE provider_id = 'openrouter'"
    )
