"""add new filetype enum values

Revision ID: 9d7325185192
Revises: 9d7325185191
Create Date: 2026-07-16 12:24:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9d7325185192"
down_revision: Union[str, Sequence[str], None] = "9d7325185191"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE filetype ADD VALUE 'xls'")
            op.execute("ALTER TYPE filetype ADD VALUE 'xlsm'")
            op.execute("ALTER TYPE filetype ADD VALUE 'xlsb'")
            op.execute("ALTER TYPE filetype ADD VALUE 'tsv'")
            op.execute("ALTER TYPE filetype ADD VALUE 'ods'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
