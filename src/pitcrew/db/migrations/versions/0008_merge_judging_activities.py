"""Merge the activities checking_pipeline and reading_testops into judging_run

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JUDGING_RUN = "judging_run"
OLD_ACTIVITIES = ("checking_pipeline", "reading_testops")

run_chains = sa.table("run_chains", sa.column("activity", sa.String()))


def upgrade() -> None:
    op.execute(
        run_chains.update()
        .where(run_chains.c.activity.in_(OLD_ACTIVITIES))
        .values(activity=JUDGING_RUN)
    )


def downgrade() -> None:
    # Which of the two a chain was in is lost; both resume by judging the Run from the start.
    op.execute(
        run_chains.update()
        .where(run_chains.c.activity == JUDGING_RUN)
        .values(activity=OLD_ACTIVITIES[0])
    )
