from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pitcrew.constants import Environment, Step
from pitcrew.db.models.base import Base, TimestampMixin, enum_type, utc_now
from pitcrew.db.models.exceptions import RerunAlreadyStartedException
from pitcrew.db.models.post import Post, PostKind
from pitcrew.db.models.run import Run, RunKind, RunOutcome, RunVerdict

MAX_FAILURE_REASON_LENGTH = 500


class Activity(StrEnum):
    """What the Run chain is doing now, in the Step it names (`RunChain.current_step`).

    Attributes:
        JUDGING_RUN: Reading the pipeline and the launch of a Run to decide its Run outcome.
        STARTING_RERUN: The Nightly run is judged *with failures*: writing its Failed tests
            into the Rerun test plan and creating the Rerun pipeline.
        RECOGNIZING_ERROR_GROUPS: Reading the errors of the Failed tests of the Rerun and
            grouping them.
        WAITING_FOR_TRIGGER: The Rerun pipeline runs; the chain goes on with its
            `night_rerun` trigger.
        POSTING_CONCLUSION: The Run chain's last Run is judged: posting the Conclusion.
        DONE: Nothing is left to do in the Step.
        FAILED: The Step failed (`RunChain.failure_reason` says why); a repeated trigger
            runs it again from its start.
    """

    JUDGING_RUN = "judging_run"
    STARTING_RERUN = "starting_rerun"
    RECOGNIZING_ERROR_GROUPS = "recognizing_error_groups"
    WAITING_FOR_TRIGGER = "waiting_for_trigger"
    POSTING_CONCLUSION = "posting_conclusion"
    DONE = "done"
    FAILED = "failed"


class RunChain(TimestampMixin, Base):
    """One night of one Team: its Runs (the Nightly run, then the Rerun) and its Slack posts.
    The Nightly run's Run is created together with the chain (`for_nightly_run`).

    The chain moves only through its transition methods. They call no client and do not
    commit: the caller saves the chain (`RunChainRepository.save`) after every one, so that
    `GET /run-chains/{trace_id}` shows it live and a resumed Step starts from it.

    Attributes:
        trace_id: The id a caller follows the whole chain by: answered to every trigger, in
            every log line.
        current_step: The Step running now; `activity` is what it is doing.
        failure_reason: Why the current Step failed (`Activity.FAILED`): the exception's
            type and message, masked and cut short; `None` while it has not failed.
        runs: The chain's Runs in the order they were started, at most one of each kind.
        posts: The Slack posts Pitcrew made about the chain, at most one of each kind and key.
    """

    __tablename__ = "run_chains"

    id: Mapped[int] = mapped_column(primary_key=True)
    trace_id: Mapped[UUID] = mapped_column(Uuid, unique=True, default=uuid4)
    team: Mapped[str] = mapped_column(String(64))
    environment: Mapped[Environment] = mapped_column(enum_type(Environment, 64))
    current_step: Mapped[Step] = mapped_column(enum_type(Step, 16))
    activity: Mapped[Activity] = mapped_column(enum_type(Activity, 32))
    failure_reason: Mapped[str | None] = mapped_column(
        String(MAX_FAILURE_REASON_LENGTH)
    )
    runs: Mapped[list[Run]] = relationship(order_by=Run.id, lazy="selectin")
    posts: Mapped[list[Post]] = relationship(order_by=Post.id, lazy="selectin")

    @classmethod
    def for_nightly_run(
        cls, *, team: str, environment: Environment, pipeline_id: int, launch_id: int
    ) -> "RunChain":
        """A new Run chain, started by its Nightly run: in the `night_run` Step, about to
        judge it.

        Args:
            team: The Team of the Nightly run.
            environment: The Environment it ran on.
            pipeline_id: Its pipeline.
            launch_id: Its Allure launch.
        """
        return cls(
            team=team,
            environment=environment,
            current_step=Step.NIGHT_RUN,
            activity=Activity.JUDGING_RUN,
            runs=[
                Run(kind=RunKind.NIGHTLY, pipeline_id=pipeline_id, launch_id=launch_id)
            ],
        )

    @property
    def nightly_run(self) -> Run:
        """The Run that started the chain."""
        nightly_run = self.run_of(RunKind.NIGHTLY)
        assert nightly_run is not None, "created together with the chain"
        return nightly_run

    @property
    def rerun(self) -> Run | None:
        """`None` until Pitcrew starts the Rerun pipeline."""
        return self.run_of(RunKind.RERUN)

    def run_of(self, kind: RunKind) -> Run | None:
        """The chain's Run of the kind; `None` while there is none.

        Args:
            kind: Which Run.
        """
        return next((run for run in self.runs if run.kind == kind), None)

    def has_finished(self, step: Step) -> bool:
        """Whether the Step has finished on the chain, told by where the chain is: a Step
        has finished once the chain has moved past it or is done in it.

        Args:
            step: The Step asked about.
        """
        steps = list(Step)
        if steps.index(self.current_step) > steps.index(step):
            return True
        return self.current_step == step and self.activity == Activity.DONE

    def set_activity(self, step: Step, activity: Activity) -> None:
        """Records what the chain is doing now; a Step running again after it failed is no
        longer failed, so the failure reason goes.

        Args:
            step: The Step running now.
            activity: What it is doing.
        """
        self.current_step = step
        self.activity = activity
        self.failure_reason = None

    def record_failure(self, reason: str) -> None:
        """Marks the current Step failed, with why. It counts as not finished
        (`has_finished`), so a repeated trigger runs it again from its start.

        Args:
            reason: Why it failed, already masked: it is cut to
                `MAX_FAILURE_REASON_LENGTH` here, and the API shows it.
        """
        self.activity = Activity.FAILED
        self.failure_reason = reason[:MAX_FAILURE_REASON_LENGTH]

    def record_judgement(
        self, run: Run, verdict: RunVerdict, *, starting_rerun: bool = False
    ) -> None:
        """Records a Run's verdict on it and moves the chain on, in one transition, so that a
        Step failing in between cannot leave the judgement without the move:

        - a broken Nightly run, or the Rerun: to `posting_conclusion` in the Run's Step (not
          `done`: the Step finishes once the Conclusion is posted, `record_conclusion`);
        - a Nightly run *with failures* whose Rerun the Step is starting: to
          `starting_rerun`, still in `night_run` (`start_rerun` moves the chain on);
        - any other Nightly run: to `night_rerun` / `waiting_for_trigger` when the chain has
          its Rerun already, otherwise `done`.

        Recording it again overwrites it.

        Args:
            run: The Run judged, one of the chain's.
            verdict: What judging it found.
            starting_rerun: The Step starts the Rerun of this Nightly run next.
        """
        run.outcome = verdict.outcome
        run.outcome_reason = verdict.reason
        run.failed_test_count = verdict.failed_test_count
        run.expected_test_count = verdict.expected_test_count
        step = Step.NIGHT_RUN if run.kind == RunKind.NIGHTLY else Step.NIGHT_RERUN
        if run.kind == RunKind.RERUN or verdict.outcome == RunOutcome.BROKEN:
            self.set_activity(step, Activity.POSTING_CONCLUSION)
        elif self.rerun is not None:
            self.set_activity(Step.NIGHT_RERUN, Activity.WAITING_FOR_TRIGGER)
        elif starting_rerun:
            self.set_activity(step, Activity.STARTING_RERUN)
        else:
            self.set_activity(step, Activity.DONE)

    def start_rerun(self, pipeline_id: int, test_case_count: int) -> Run:
        """Records the Rerun Pitcrew started as the chain's Rerun and moves the chain on to
        waiting for its `night_rerun` trigger.

        Args:
            pipeline_id: The Rerun pipeline.
            test_case_count: The test cases written into the Rerun test plan: the Rerun's
                expected size.

        Raises:
            RerunAlreadyStartedException: The chain has a Rerun already; it is kept.
        """
        if self.rerun is not None:
            raise RerunAlreadyStartedException(
                f"Run chain {self.trace_id} has its Rerun already: pipeline "
                f"{self.rerun.pipeline_id}"
            )
        rerun = Run(
            kind=RunKind.RERUN,
            pipeline_id=pipeline_id,
            expected_test_count=test_case_count,
        )
        self.runs.append(rerun)
        self.set_activity(Step.NIGHT_RERUN, Activity.WAITING_FOR_TRIGGER)
        return rerun

    def accept_rerun_launch(self, launch_id: int) -> None:
        """Records the Allure launch of the chain's Rerun, once: a launch accepted before is
        kept, so accepting one again changes nothing.

        Args:
            launch_id: The launch its `night_rerun` trigger brought.
        """
        rerun = self.rerun
        assert rerun is not None, "the chain was found by its Rerun"
        if rerun.launch_id is None:
            rerun.launch_id = launch_id

    def post_of(self, kind: PostKind, key: str = "") -> Post | None:
        """The chain's Slack post of the kind and key; `None` while there is none.

        Args:
            kind: What the post is.
            key: Which post of the kind; empty for the Conclusion.
        """
        return next(
            (post for post in self.posts if post.kind == kind and post.key == key),
            None,
        )

    def has_post(self, kind: PostKind, key: str = "") -> bool:
        """Whether the chain has its Slack post of the kind and key.

        Args:
            kind: What the post is.
            key: Which post of the kind; empty for the Conclusion.
        """
        return self.post_of(kind, key) is not None

    def record_post(self, kind: PostKind, key: str = "") -> Post:
        """Records a Slack post Slack accepted just now. The chain holds one post of each
        kind and key: a second record of one is refused by the store when saved, so a caller
        asks `has_post` first.

        Args:
            kind: What the post is.
            key: Which post of the kind; empty for the Conclusion.
        """
        post = Post(kind=kind, key=key, posted_at=utc_now())
        self.posts.append(post)
        return post

    def record_conclusion(self) -> None:
        """Finishes the Step that concluded the chain, whether or not it has its Conclusion
        (a Team without a Slack Conclusion has none): the post itself is recorded by
        `record_post`."""
        self.activity = Activity.DONE
