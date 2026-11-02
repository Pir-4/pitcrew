from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pitcrew.db.models.base import Base, TimestampMixin, enum_type


class RunKind(StrEnum):
    """Which Run of the Run chain a Run is (`CONTEXT.md`).

    Attributes:
        NIGHTLY: The scheduled pipeline that starts the Run chain.
        RERUN: The pipeline Pitcrew started to run the Failed tests of the Nightly run again.
    """

    NIGHTLY = "nightly"
    RERUN = "rerun"


class RunOutcome(StrEnum):
    """Pitcrew's verdict on a finished Run (see `CONTEXT.md`)."""

    GREEN = "green"
    WITH_FAILURES = "with_failures"
    BROKEN = "broken"


@dataclass(frozen=True)
class RunVerdict:
    """What judging a Run found that is written onto it (`RunChain.record_judgement`).

    Attributes:
        outcome: The Run outcome.
        reason: Why the Run is broken, in words; `None` unless it is.
        failed_test_count: Its Failed tests; `None` when they were not read.
        expected_test_count: Its expected size.
    """

    outcome: RunOutcome
    reason: str | None
    failed_test_count: int | None
    expected_test_count: int | None


class Run(TimestampMixin, Base):
    """One `qa_automation` pipeline of a Run chain and its Allure launch, which Pitcrew
    judges. A Run chain holds at most one Run of each kind; a pipeline belongs to at most one
    Run, so that a trigger's pipeline finds exactly one Run chain.

    Attributes:
        launch_id: `None` until known: a Rerun's launch arrives with its `night_rerun`
            trigger.
        expected_test_count: The Run's expected size: the test cases of the Team's nightly
            test plan for a Nightly run, the ones written into the Rerun test plan for a
            Rerun. `None` while it was not read.
        failed_test_count: `None` while the Failed tests were not read (a broken pipeline's
            never are).
        outcome: `None` until the Run is judged.
        outcome_reason: Why the Run is broken, in words, e.g. `1 result out of ~1675
            expected`; `None` unless it is.
    """

    __tablename__ = "runs"
    __table_args__ = (UniqueConstraint("run_chain_id", "kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_chain_id: Mapped[int] = mapped_column(ForeignKey("run_chains.id"), index=True)
    kind: Mapped[RunKind] = mapped_column(enum_type(RunKind, 16))
    pipeline_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    launch_id: Mapped[int | None] = mapped_column(BigInteger)
    expected_test_count: Mapped[int | None] = mapped_column(Integer)
    failed_test_count: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[RunOutcome | None] = mapped_column(enum_type(RunOutcome, 16))
    outcome_reason: Mapped[str | None] = mapped_column(String(255))
