"""Add the trace id, the chain's status, the Rerun and the Conclusion to run_chains

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-19

"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("run_chains", sa.Column("trace_id", sa.Uuid(), nullable=True))
    op.add_column("run_chains", sa.Column("current_step", sa.String(16), nullable=True))
    op.add_column("run_chains", sa.Column("activity", sa.String(32), nullable=True))
    for name, type_ in (
        ("rerun_test_case_count", sa.Integer()),
        ("rerun_launch_id", sa.BigInteger()),
        ("night_rerun_status", sa.String(16)),
        ("rerun_failed_test_count", sa.Integer()),
        ("rerun_outcome", sa.String(16)),
        ("rerun_outcome_reason", sa.String(255)),
        ("conclusion_posted_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("run_chains", sa.Column(name, type_, nullable=True))

    # The chains recorded so far get a trace id each and the status of their `night_run`.
    connection = op.get_bind()
    run_chains = sa.table(
        "run_chains",
        sa.column("id", sa.Integer()),
        sa.column("trace_id", sa.Uuid()),
        sa.column("current_step", sa.String()),
        sa.column("activity", sa.String()),
        sa.column("night_run_status", sa.String()),
        sa.column("rerun_pipeline_id", sa.BigInteger()),
    )
    for chain in connection.execute(sa.select(run_chains)).all():
        if chain.night_run_status != "finished":
            activity = "reading_testops"
        elif chain.rerun_pipeline_id is not None:
            activity = "waiting_for_trigger"
        else:
            activity = "done"
        connection.execute(
            run_chains.update()
            .where(run_chains.c.id == chain.id)
            .values(
                trace_id=uuid4(),
                current_step=(
                    "night_rerun" if activity == "waiting_for_trigger" else "night_run"
                ),
                activity=activity,
            )
        )

    with op.batch_alter_table("run_chains") as batch:
        batch.alter_column("trace_id", existing_type=sa.Uuid(), nullable=False)
        batch.alter_column("current_step", existing_type=sa.String(16), nullable=False)
        batch.alter_column("activity", existing_type=sa.String(32), nullable=False)
        batch.create_unique_constraint("uq_run_chains_trace_id", ["trace_id"])


def downgrade() -> None:
    with op.batch_alter_table("run_chains") as batch:
        batch.drop_constraint("uq_run_chains_trace_id", type_="unique")
        for name in (
            "conclusion_posted_at",
            "rerun_outcome_reason",
            "rerun_outcome",
            "rerun_failed_test_count",
            "night_rerun_status",
            "rerun_launch_id",
            "rerun_test_case_count",
            "activity",
            "current_step",
            "trace_id",
        ):
            batch.drop_column(name)
