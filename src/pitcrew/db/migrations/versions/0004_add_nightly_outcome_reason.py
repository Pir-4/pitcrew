"""Add the reason of the Nightly run's outcome to run_chains

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "run_chains",
        sa.Column("nightly_outcome_reason", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("run_chains", "nightly_outcome_reason")
