"""The Error groups of a Run chain: Failed tests of the Rerun that fail for one cause
Pitcrew recognized (`ErrorGroup` with its `ErrorGroupTest`s), and the values the Error
group rule hands over before they are stored (`NewErrorGroup`, `NewErrorGroupTest`)."""

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pitcrew.db.models.base import Base, TimestampMixin, enum_type


class ErrorKind(StrEnum):
    """The sort of cause behind an Error group (`CONTEXT.md`).

    Attributes:
        MODEL: A pydantic model of the tests (an API response schema or a database model)
            rejected the data; keyed by the model's name as the error writes it.
    """

    MODEL = "model"


@dataclass(frozen=True)
class NewErrorGroupTest:
    """A Failed test of a recognized Error group, not stored yet (`ErrorGroupTest` once it
    is).

    Attributes:
        test_case_id: `None` for a result TestOps has not linked to a test case.
    """

    test_result_id: int
    test_case_id: int | None
    name: str


@dataclass(frozen=True)
class NewErrorGroup:
    """An Error group recognized among the Failed tests of the Rerun and not stored yet:
    what the Error group rule (`steps/error_groups.py`) answers and `ErrorGroupService`
    stores.

    Attributes:
        key: What broke, as the error names it (`ErrorGroup.key`).
    """

    kind: ErrorKind
    key: str
    tests: tuple[NewErrorGroupTest, ...]


class ErrorGroup(TimestampMixin, Base):
    """Failed tests of the Rerun of a Run chain that fail for one cause Pitcrew recognizes.

    Attributes:
        key: What broke, as the error names it, e.g. `DataResponse[RoutersOverview]`.
    """

    __tablename__ = "error_groups"
    __table_args__ = (UniqueConstraint("run_chain_id", "kind", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_chain_id: Mapped[int] = mapped_column(ForeignKey("run_chains.id"), index=True)
    kind: Mapped[ErrorKind] = mapped_column(enum_type(ErrorKind, 16))
    key: Mapped[str] = mapped_column(String(255))
    # Read only: the tests are written through `ErrorGroupTestRepository`.
    tests: Mapped[list["ErrorGroupTest"]] = relationship(
        order_by="ErrorGroupTest.id", lazy="selectin", viewonly=True
    )

    @property
    def test_count(self) -> int:
        return len(self.tests)


class ErrorGroupTest(Base):
    """A Failed test of the Rerun in an Error group: its result in the Rerun launch and its
    test case, the one a fix runs again.

    Attributes:
        test_case_id: `None` for a result TestOps has not linked to a test case.
    """

    __tablename__ = "error_group_tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    error_group_id: Mapped[int] = mapped_column(
        ForeignKey("error_groups.id"), index=True
    )
    test_result_id: Mapped[int] = mapped_column(BigInteger)
    test_case_id: Mapped[int | None] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(512))
