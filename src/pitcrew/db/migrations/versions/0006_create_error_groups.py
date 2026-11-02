"""Create error_groups and error_group_tests

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "error_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_chain_id",
            sa.Integer(),
            sa.ForeignKey(
                "run_chains.id", name="fk_error_groups_run_chain_id_run_chains"
            ),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "run_chain_id", "kind", "key", name="uq_error_groups_run_chain_id"
        ),
    )
    op.create_index("ix_error_groups_run_chain_id", "error_groups", ["run_chain_id"])
    op.create_table(
        "error_group_tests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "error_group_id",
            sa.Integer(),
            sa.ForeignKey(
                "error_groups.id",
                name="fk_error_group_tests_error_group_id_error_groups",
            ),
            nullable=False,
        ),
        sa.Column("test_result_id", sa.BigInteger(), nullable=False),
        sa.Column("test_case_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(512), nullable=False),
    )
    op.create_index(
        "ix_error_group_tests_error_group_id", "error_group_tests", ["error_group_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_error_group_tests_error_group_id", table_name="error_group_tests")
    op.drop_table("error_group_tests")
    op.drop_index("ix_error_groups_run_chain_id", table_name="error_groups")
    op.drop_table("error_groups")
