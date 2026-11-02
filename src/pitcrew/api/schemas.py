"""Request and response bodies of the API."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field

from pitcrew.constants import Step
from pitcrew.db.models.error_group import ErrorGroup, ErrorKind
from pitcrew.db.models.post import PostKind
from pitcrew.db.models.run import Run, RunKind, RunOutcome
from pitcrew.db.models.run_chain import Activity, RunChain
from pitcrew.steps.trigger import Trigger


def _in_utc(value: datetime) -> datetime:
    # SQLite drops the timezone the timestamps were written with; they are always UTC.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


type UtcDatetime = Annotated[datetime, AfterValidator(_in_utc)]


class TriggerRequest(Trigger):
    """Body of `POST /triggers`: a Step of a Team's Run chain has finished on an Environment.

    `team` is any Team with a Team config, in any spelling (`Gateway`, `gateway`): the
    Run chain shows it as its Team config spells it."""


class TriggerResponse(BaseModel):
    """Body of the `POST /triggers` answer: the Run chain the trigger belongs to, followed
    through `GET /run-chains/{trace_id}`."""

    trace_id: UUID


class ChainStatus(BaseModel):
    """The Step running now and what it is doing; `done` once nothing is left to do,
    `failed` when it failed (the chain's `failure_reason` says why)."""

    step: Step
    activity: Activity


class RunResponse(BaseModel):
    """A Run of the Run chain: its pipeline and launch, and what Pitcrew found judging it."""

    kind: RunKind
    pipeline_id: int
    launch_id: int | None = Field(
        description="`None` until known: a Rerun's launch arrives with its trigger"
    )
    expected_test_count: int | None = Field(
        description="The test cases of the nightly test plan for a Nightly run, the ones "
        "written into the Rerun test plan for a Rerun; `None` while not read"
    )
    failed_test_count: int | None = Field(
        description="`None` while the Failed tests were not read"
    )
    outcome: RunOutcome | None = Field(description="`None` until the Run is judged")
    outcome_reason: str | None = Field(description="Why the Run is broken, in words")

    @classmethod
    def from_run(cls, run: Run) -> Self:
        """
        Args:
            run: The stored Run.
        """
        return cls(
            kind=run.kind,
            pipeline_id=run.pipeline_id,
            launch_id=run.launch_id,
            expected_test_count=run.expected_test_count,
            failed_test_count=run.failed_test_count,
            outcome=run.outcome,
            outcome_reason=run.outcome_reason,
        )


class ErrorGroupTestResponse(BaseModel):
    """A Failed test of the Rerun in an Error group."""

    test_result_id: int
    test_case_id: int | None
    name: str


class ErrorGroupResponse(BaseModel):
    """Failed tests of the Rerun that fail for one cause Pitcrew recognized."""

    kind: ErrorKind
    key: str = Field(description="What broke, as the error names it, e.g. the model")
    test_count: int
    tests: list[ErrorGroupTestResponse]

    @classmethod
    def from_group(cls, group: ErrorGroup) -> Self:
        """
        Args:
            group: The stored Error group, with its tests.
        """
        return cls(
            kind=group.kind,
            key=group.key,
            test_count=group.test_count,
            tests=[
                ErrorGroupTestResponse(
                    test_result_id=test.test_result_id,
                    test_case_id=test.test_case_id,
                    name=test.name,
                )
                for test in group.tests
            ],
        )


class ConclusionResponse(BaseModel):
    """The Conclusion posted to the Team's Slack channel."""

    posted_at: UtcDatetime


class RunChainResponse(BaseModel):
    """Body of `GET /run-chains/{trace_id}`: the status of the whole Run chain, its Runs in
    the order they were started; `conclusion` is `None` while there is none. `error_groups`
    are the ones recognized among the Failed tests of the Rerun, largest first."""

    trace_id: UUID
    team: str
    environment: str
    status: ChainStatus
    failure_reason: str | None = Field(
        description="Why the Step in `status` failed (`failed`): the error's type and "
        "message, secrets masked, cut short; `None` while it has not failed. A repeated "
        "trigger runs the Step again and clears it"
    )
    runs: list[RunResponse]
    error_groups: list[ErrorGroupResponse]
    conclusion: ConclusionResponse | None
    created_at: UtcDatetime
    updated_at: UtcDatetime

    @classmethod
    def from_chain(cls, chain: RunChain, error_groups: Sequence[ErrorGroup]) -> Self:
        """
        Args:
            chain: The stored Run chain.
            error_groups: The Error groups of the chain, largest first.
        """
        conclusion = chain.post_of(PostKind.CONCLUSION)
        return cls(
            trace_id=chain.trace_id,
            team=chain.team,
            environment=chain.environment,
            status=ChainStatus(step=chain.current_step, activity=chain.activity),
            failure_reason=chain.failure_reason,
            runs=[RunResponse.from_run(run) for run in chain.runs],
            error_groups=[
                ErrorGroupResponse.from_group(group) for group in error_groups
            ],
            conclusion=None
            if conclusion is None
            else ConclusionResponse(posted_at=conclusion.posted_at),
            created_at=chain.created_at,
            updated_at=chain.updated_at,
        )
