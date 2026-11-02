"""One module per table. Every model is imported here so that `Base.metadata` knows all
tables once this package is imported: Alembic autogenerate compares the DB against it."""

from pitcrew.db.models.base import Base
from pitcrew.db.models.error_group import (
    ErrorGroup,
    ErrorGroupTest,
    ErrorKind,
    NewErrorGroup,
    NewErrorGroupTest,
)
from pitcrew.db.models.post import Post, PostKind
from pitcrew.db.models.run import Run, RunKind, RunOutcome, RunVerdict
from pitcrew.db.models.run_chain import Activity, RunChain

__all__ = [
    "Activity",
    "Base",
    "ErrorGroup",
    "ErrorGroupTest",
    "ErrorKind",
    "NewErrorGroup",
    "NewErrorGroupTest",
    "Post",
    "PostKind",
    "Run",
    "RunChain",
    "RunKind",
    "RunOutcome",
    "RunVerdict",
]
