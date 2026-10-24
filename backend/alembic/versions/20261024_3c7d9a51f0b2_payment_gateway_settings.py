"""payment gateway settings editable from the admin

Additive only: one new table. Until a row is saved from Admin > Payment gateway
the application keeps using PAYMENT_MODE and the RAZORPAY_* variables.

Rollback: `alembic downgrade e52a1c1bd47a` drops the table, which discards any
keys entered in the admin (the environment variables then apply again).

Revision ID: 3c7d9a51f0b2
Revises: e52a1c1bd47a
Create Date: 2026-10-24 10:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3c7d9a51f0b2'  # pragma: allowlist secret
down_revision: Union[str, None] = 'e52a1c1bd47a'  # pragma: allowlist secret
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('payment_gateway_settings',
    sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('mode', sa.String(length=16), nullable=False),
    sa.Column('key_id', sa.String(length=64), nullable=False),
    sa.Column('key_secret_enc', sa.Text(), nullable=True),
    sa.Column('webhook_secret_enc', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('updated_by_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['updated_by_id'], ['admin_users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('payment_gateway_settings')
