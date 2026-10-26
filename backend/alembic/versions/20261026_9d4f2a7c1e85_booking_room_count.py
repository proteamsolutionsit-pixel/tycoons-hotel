"""multi-room bookings: bookings.room_count

Additive: one NOT NULL column defaulting to 1, so every existing booking is
exactly what it was (one room). Plus a check constraint room_count >= 1.

Rollback: `alembic downgrade 7b1e4c2d9a60` drops the column; any booking for
more than one room would then read as a single room - export those first.

Revision ID: 9d4f2a7c1e85
Revises: 7b1e4c2d9a60
Create Date: 2026-10-26 12:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9d4f2a7c1e85'  # pragma: allowlist secret
down_revision: Union[str, None] = '7b1e4c2d9a60'  # pragma: allowlist secret
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bookings', sa.Column('room_count', sa.Integer(), server_default='1', nullable=False))
    op.create_check_constraint(op.f('ck_bookings_room_count_positive'), 'bookings', 'room_count >= 1')


def downgrade() -> None:
    op.drop_constraint(op.f('ck_bookings_room_count_positive'), 'bookings', type_='check')
    op.drop_column('bookings', 'room_count')
