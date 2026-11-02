"""The Slack posts Pitcrew made about a Run chain, one record per post."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pitcrew.db.models.base import Base, enum_type


class PostKind(StrEnum):
    """What a Slack post of Pitcrew about a Run chain is.

    Attributes:
        CONCLUSION: The Conclusion of the Run chain (`CONTEXT.md`).
    """

    CONCLUSION = "conclusion"


class Post(Base):
    """A Slack post Pitcrew made about a Run chain. A chain holds at most one post of each
    kind and key, so that a resumed Step finds the post it made and does not post it again.

    Attributes:
        key: Tells apart the posts of one kind on one chain; empty for the Conclusion, the
            only one of its kind.
        posted_at: When Slack accepted the post.
    """

    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("run_chain_id", "kind", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_chain_id: Mapped[int] = mapped_column(ForeignKey("run_chains.id"), index=True)
    kind: Mapped[PostKind] = mapped_column(enum_type(PostKind, 16))
    key: Mapped[str] = mapped_column(String(255), default="")
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
