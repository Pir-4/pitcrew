"""Add the Nightly run outcome to run_chains

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "run_chains",
        sa.Column("nightly_failed_test_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "run_chains", sa.Column("nightly_outcome", sa.String(16), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("run_chains", "nightly_outcome")
    op.drop_column("run_chains", "nightly_failed_test_count")
