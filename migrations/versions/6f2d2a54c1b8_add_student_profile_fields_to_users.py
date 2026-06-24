"""Add student profile fields to users.

Revision ID: 6f2d2a54c1b8
Revises: 000f4c9c67dd
Create Date: 2026-06-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6f2d2a54c1b8"
down_revision: Union[str, Sequence[str], None] = "000f4c9c67dd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(length=100), nullable=True))
    op.add_column(
        "users",
        sa.Column("department", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "department")
    op.drop_column("users", "name")
