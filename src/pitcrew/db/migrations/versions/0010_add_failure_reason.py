"""Add run_chains.failure_reason: why the current Step failed

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FAILED = "failed"
JUDGING_RUN = "judging_run"

run_chains = sa.table("run_chains", sa.column("activity", sa.String()))


def upgrade() -> None:
    op.add_column(
        "run_chains",
        sa.Column("failure_reason", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    # The old schema has no `failed`: a failed Step goes back to the first activity of
    # every Step, from which a repeated trigger runs it again from its start, as it would
    # run a failed one.
    op.execute(
        run_chains.update()
        .where(run_chains.c.activity == FAILED)
        .values(activity=JUDGING_RUN)
    )
    with op.batch_alter_table("run_chains") as batch:
        batch.drop_column("failure_reason")
