"""Create posts: move each chain's conclusion_posted_at into a conclusion post

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONCLUSION = "conclusion"

posts = sa.table(
    "posts",
    sa.column("run_chain_id", sa.Integer()),
    sa.column("kind", sa.String()),
    sa.column("key", sa.String()),
    sa.column("posted_at", sa.DateTime(timezone=True)),
)
run_chains = sa.table(
    "run_chains",
    sa.column("id", sa.Integer()),
    sa.column("conclusion_posted_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_chain_id",
            sa.Integer(),
            sa.ForeignKey("run_chains.id", name="fk_posts_run_chain_id_run_chains"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "run_chain_id", "kind", "key", name="uq_posts_run_chain_id"
        ),
    )
    op.create_index("ix_posts_run_chain_id", "posts", ["run_chain_id"])

    connection = op.get_bind()
    posted = connection.execute(
        sa.select(run_chains).where(run_chains.c.conclusion_posted_at.is_not(None))
    ).mappings()
    for chain in posted.all():
        connection.execute(
            posts.insert().values(
                run_chain_id=chain["id"],
                kind=CONCLUSION,
                key="",
                posted_at=chain["conclusion_posted_at"],
            )
        )

    with op.batch_alter_table("run_chains") as batch:
        batch.drop_column("conclusion_posted_at")


def downgrade() -> None:
    op.add_column(
        "run_chains",
        sa.Column("conclusion_posted_at", sa.DateTime(timezone=True), nullable=True),
    )

    connection = op.get_bind()
    conclusions = connection.execute(
        sa.select(posts).where(posts.c.kind == CONCLUSION, posts.c.key == "")
    ).mappings()
    for post in conclusions.all():
        connection.execute(
            run_chains.update()
            .where(run_chains.c.id == post["run_chain_id"])
            .values(conclusion_posted_at=post["posted_at"])
        )

    op.drop_index("ix_posts_run_chain_id", table_name="posts")
    op.drop_table("posts")
