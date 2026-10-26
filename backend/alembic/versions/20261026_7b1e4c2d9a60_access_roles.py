"""access roles: administrator-defined roles with per-permission access

Additive: a `roles` table and a nullable admin_users.role_id. Seeds the two
built-in roles and assigns every existing user the one matching their current
access (admin -> Administrator, staff -> Front desk), so nobody's rights
change. The legacy admin_users.role column is kept and stays in step.

Rollback: `alembic downgrade 3c7d9a51f0b2` drops role_id and the roles table;
users fall back to their legacy admin/staff role. Custom roles are lost.

Revision ID: 7b1e4c2d9a60
Revises: 3c7d9a51f0b2
Create Date: 2026-10-26 11:00:00
"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7b1e4c2d9a60'  # pragma: allowlist secret
down_revision: Union[str, None] = '3c7d9a51f0b2'  # pragma: allowlist secret
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FRONT_DESK = ["dashboard.view", "bookings.view", "payments.view", "submissions.view", "submissions.manage",
              "catalog.view"]


def upgrade() -> None:
    roles = op.create_table('roles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=32), nullable=True),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('permissions', sa.JSON(), nullable=False),
    sa.Column('is_system', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key'),
    sa.UniqueConstraint('name')
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    op.bulk_insert(roles, [
        {"id": 1, "key": "administrator", "name": "Administrator", "is_system": True, "permissions": [],
         "description": "Full access to everything, including roles and payment keys.", "created_at": now, "updated_at": now},
        {"id": 2, "key": "front_desk", "name": "Front desk", "is_system": False, "permissions": FRONT_DESK,
         "description": "Bookings and payments (read), guest requests, rooms and content (read).",
         "created_at": now, "updated_at": now},
    ])
    op.add_column('admin_users', sa.Column('role_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_admin_users_role_id'), 'admin_users', ['role_id'], unique=False)
    op.create_foreign_key('fk_admin_users_role_id_roles', 'admin_users', 'roles', ['role_id'], ['id'], ondelete='RESTRICT')
    op.execute("UPDATE admin_users SET role_id = CASE WHEN role = 'admin' THEN 1 ELSE 2 END")


def downgrade() -> None:
    op.drop_constraint('fk_admin_users_role_id_roles', 'admin_users', type_='foreignkey')
    op.drop_index(op.f('ix_admin_users_role_id'), table_name='admin_users')
    op.drop_column('admin_users', 'role_id')
    op.drop_table('roles')
