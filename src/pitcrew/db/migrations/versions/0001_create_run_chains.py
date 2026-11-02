"""Create run_chains

Revision ID: 0001
Revises:
Create Date: 2026-10-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "run_chains",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(64), nullable=False),
        sa.Column("nightly_pipeline_id", sa.BigInteger(), nullable=False),
        sa.Column("nightly_launch_id", sa.BigInteger(), nullable=False),
        sa.Column("night_run_status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "nightly_pipeline_id", name="uq_run_chains_nightly_pipeline_id"
        ),
    )


def downgrade() -> None:
    op.drop_table("run_chains")
