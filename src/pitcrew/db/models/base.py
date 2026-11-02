"""What every model shares: the declarative `Base` with the constraint naming convention,
the UTC timestamps (`TimestampMixin`, `utc_now`) and the type of a status column
(`enum_type`)."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Constraint and index names are derived from the table and columns instead of left to the DB,
# so they are the same on SQLite and MySQL and a later migration can drop or alter them by name.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    """`created_at` and `updated_at` in UTC, set by the ORM on insert and on every update."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


def enum_type[E: StrEnum](enum_class: type[E], length: int) -> Enum:
    """The column type of a status stored as its enum's value: it reads the enum member
    back and refuses, when written, a string that is none of the enum's values.

    A plain `VARCHAR` of the given length with no CHECK constraint, so that adding a member
    needs no migration; an enum member renamed or merged needs one, to move the stored
    values (`AGENTS.md`).

    Args:
        enum_class: The enum the column holds.
        length: The column's length, at least the longest value.
    """
    return Enum(
        enum_class,
        native_enum=False,
        create_constraint=False,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
        length=length,
    )
