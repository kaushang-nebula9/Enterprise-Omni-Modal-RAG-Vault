"""add hierarchical role access columns

Revision ID: c7a8b9d0e1f2
Revises: a1b2c3d4e5f6
Create Date: 2026-06-23 13:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7a8b9d0e1f2'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add parent_role_id to roles table (self-referencing foreign key)
    op.add_column('roles', sa.Column('parent_role_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_roles_parent_role_id',
        'roles',
        'roles',
        ['parent_role_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Add granted_via and inherited_from_role_id to document_access_policies
    op.add_column(
        'document_access_policies',
        sa.Column('granted_via', sa.String(), nullable=False, server_default='direct')
    )
    op.add_column(
        'document_access_policies',
        sa.Column('inherited_from_role_id', sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        'fk_dap_inherited_from_role_id',
        'document_access_policies',
        'roles',
        ['inherited_from_role_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    # Remove inherited_from_role_id FK and column
    op.drop_constraint('fk_dap_inherited_from_role_id', 'document_access_policies', type_='foreignkey')
    op.drop_column('document_access_policies', 'inherited_from_role_id')
    op.drop_column('document_access_policies', 'granted_via')

    # Remove parent_role_id FK and column
    op.drop_constraint('fk_roles_parent_role_id', 'roles', type_='foreignkey')
    op.drop_column('roles', 'parent_role_id')
