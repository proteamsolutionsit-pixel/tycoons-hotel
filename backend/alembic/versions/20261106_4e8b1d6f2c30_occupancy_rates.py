"""occupancy-based rates: single-occupancy rate and inclusions per room type

Additive and data-neutral:
* room_types.single_rate_paise (NULL = standard rate for every occupancy) and
  room_types.inclusions ('' = none);
* bookings.single_room_count (0), bookings.single_rate_paise (NULL) and
  bookings.inclusions (NULL) record what the guest was quoted.
Existing prices and bookings are unchanged.

Rollback: `alembic downgrade 9d4f2a7c1e85` drops the five columns; bookings
priced at the single rate keep their stored totals but lose the breakdown.

Revision ID: 4e8b1d6f2c30
Revises: 9d4f2a7c1e85
Create Date: 2026-11-06 10:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4e8b1d6f2c30'  # pragma: allowlist secret
down_revision: Union[str, None] = '9d4f2a7c1e85'  # pragma: allowlist secret
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('room_types', sa.Column('single_rate_paise', sa.Integer(), nullable=True))
    op.add_column('room_types', sa.Column('inclusions', sa.String(length=255), server_default='', nullable=False))
    op.create_check_constraint(op.f('ck_room_types_single_rate_non_negative'), 'room_types',
                               'single_rate_paise IS NULL OR single_rate_paise >= 0')
    op.add_column('bookings', sa.Column('single_room_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('bookings', sa.Column('single_rate_paise', sa.Integer(), nullable=True))
    op.add_column('bookings', sa.Column('inclusions', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('bookings', 'inclusions')
    op.drop_column('bookings', 'single_rate_paise')
    op.drop_column('bookings', 'single_room_count')
    op.drop_constraint(op.f('ck_room_types_single_rate_non_negative'), 'room_types', type_='check')
    op.drop_column('room_types', 'inclusions')
    op.drop_column('room_types', 'single_rate_paise')
