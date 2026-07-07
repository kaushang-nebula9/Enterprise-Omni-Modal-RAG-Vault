"""rename_org_wide_to_public

Revision ID: 047d72ea7b8c
Revises: a5f3d4b6c7e8
Create Date: 2026-07-07 15:05:38.267138

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "047d72ea7b8c"
down_revision: Union[str, Sequence[str], None] = "a5f3d4b6c7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE visibility RENAME VALUE 'org_wide' TO 'public'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TYPE visibility RENAME VALUE 'public' TO 'org_wide'")
