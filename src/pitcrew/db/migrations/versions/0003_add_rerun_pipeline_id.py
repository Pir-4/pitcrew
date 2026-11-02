"""Add the Rerun pipeline id to run_chains

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "run_chains", sa.Column("rerun_pipeline_id", sa.BigInteger(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("run_chains", "rerun_pipeline_id")
