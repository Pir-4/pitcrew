"""Create runs: move each chain's Nightly run and Rerun out of run_chains

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The columns of run_chains that move into runs, by kind, as (run_chains column, runs column).
NIGHTLY_COLUMNS = (
    ("nightly_pipeline_id", "pipeline_id"),
    ("nightly_launch_id", "launch_id"),
    ("nightly_failed_test_count", "failed_test_count"),
    ("nightly_outcome", "outcome"),
    ("nightly_outcome_reason", "outcome_reason"),
)
RERUN_COLUMNS = (
    ("rerun_pipeline_id", "pipeline_id"),
    ("rerun_launch_id", "launch_id"),
    ("rerun_test_case_count", "expected_test_count"),
    ("rerun_failed_test_count", "failed_test_count"),
    ("rerun_outcome", "outcome"),
    ("rerun_outcome_reason", "outcome_reason"),
)
OLD_COLUMNS = (
    ("nightly_pipeline_id", sa.BigInteger()),
    ("nightly_launch_id", sa.BigInteger()),
    ("night_run_status", sa.String(16)),
    ("nightly_failed_test_count", sa.Integer()),
    ("nightly_outcome", sa.String(16)),
    ("nightly_outcome_reason", sa.String(255)),
    ("rerun_pipeline_id", sa.BigInteger()),
    ("rerun_test_case_count", sa.Integer()),
    ("rerun_launch_id", sa.BigInteger()),
    ("night_rerun_status", sa.String(16)),
    ("rerun_failed_test_count", sa.Integer()),
    ("rerun_outcome", sa.String(16)),
    ("rerun_outcome_reason", sa.String(255)),
)
# Not null in run_chains before this migration: the downgrade restores them so.
REQUIRED_OLD_COLUMNS = ("nightly_pipeline_id", "nightly_launch_id", "night_run_status")

runs = sa.table(
    "runs",
    sa.column("id", sa.Integer()),
    sa.column("run_chain_id", sa.Integer()),
    sa.column("kind", sa.String()),
    sa.column("pipeline_id", sa.BigInteger()),
    sa.column("launch_id", sa.BigInteger()),
    sa.column("expected_test_count", sa.Integer()),
    sa.column("failed_test_count", sa.Integer()),
    sa.column("outcome", sa.String()),
    sa.column("outcome_reason", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
run_chains = sa.table(
    "run_chains",
    sa.column("id", sa.Integer()),
    sa.column("current_step", sa.String()),
    sa.column("activity", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
    *(sa.column(name, type_) for name, type_ in OLD_COLUMNS),
)


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_chain_id",
            sa.Integer(),
            sa.ForeignKey("run_chains.id", name="fk_runs_run_chain_id_run_chains"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("pipeline_id", sa.BigInteger(), nullable=False),
        sa.Column("launch_id", sa.BigInteger(), nullable=True),
        sa.Column("expected_test_count", sa.Integer(), nullable=True),
        sa.Column("failed_test_count", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(16), nullable=True),
        sa.Column("outcome_reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("pipeline_id", name="uq_runs_pipeline_id"),
        sa.UniqueConstraint("run_chain_id", "kind", name="uq_runs_run_chain_id"),
    )
    op.create_index("ix_runs_run_chain_id", "runs", ["run_chain_id"])

    connection = op.get_bind()
    for chain in connection.execute(sa.select(run_chains)).mappings().all():
        moved = [("nightly", NIGHTLY_COLUMNS)]
        if chain["rerun_pipeline_id"] is not None:
            moved.append(("rerun", RERUN_COLUMNS))
        for kind, columns in moved:
            connection.execute(
                runs.insert().values(
                    run_chain_id=chain["id"],
                    kind=kind,
                    created_at=chain["created_at"],
                    updated_at=chain["updated_at"],
                    **{new: chain[old] for old, new in columns},
                )
            )

    with op.batch_alter_table("run_chains") as batch:
        batch.drop_constraint("uq_run_chains_nightly_pipeline_id", type_="unique")
        for name, _ in OLD_COLUMNS:
            batch.drop_column(name)


def downgrade() -> None:
    for name, type_ in OLD_COLUMNS:
        op.add_column("run_chains", sa.Column(name, type_, nullable=True))

    # The Step status columns are told again by where each chain is.
    connection = op.get_bind()
    for chain in connection.execute(sa.select(run_chains)).mappings().all():
        chain_runs = {
            run["kind"]: run
            for run in connection.execute(
                sa.select(runs).where(runs.c.run_chain_id == chain["id"])
            ).mappings()
        }
        in_rerun = chain["current_step"] == "night_rerun"
        done = chain["activity"] == "done"
        values = {
            "night_run_status": "finished" if in_rerun or done else "started",
            **{old: chain_runs["nightly"][new] for old, new in NIGHTLY_COLUMNS},
        }
        rerun = chain_runs.get("rerun")
        if rerun is not None:
            values |= {old: rerun[new] for old, new in RERUN_COLUMNS}
            if rerun["launch_id"] is not None:
                values["night_rerun_status"] = (
                    "finished" if in_rerun and done else "started"
                )
        connection.execute(
            run_chains.update().where(run_chains.c.id == chain["id"]).values(values)
        )

    with op.batch_alter_table("run_chains") as batch:
        for name, type_ in OLD_COLUMNS:
            if name in REQUIRED_OLD_COLUMNS:
                batch.alter_column(name, existing_type=type_, nullable=False)
        batch.create_unique_constraint(
            "uq_run_chains_nightly_pipeline_id", ["nightly_pipeline_id"]
        )

    op.drop_index("ix_runs_run_chain_id", table_name="runs")
    op.drop_table("runs")
