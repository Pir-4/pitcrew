from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from pitcrew.config.team import TeamConfig
from pitcrew.constants import Step
from pitcrew.db.models.error_group import ErrorGroup
from pitcrew.db.models.post import PostKind
from pitcrew.db.models.run import Run
from pitcrew.db.models.run_chain import Activity, RunChain
from pitcrew.db.repositories.container import Repositories
from pitcrew.log import bind_log_context, get_logger, log_scope, masked
from pitcrew.steps.checks import check_launch_belongs_to_pipeline
from pitcrew.steps.conclusion import conclusion_message
from pitcrew.steps.dependencies import StepDependencies
from pitcrew.steps.judging import Judgement
from pitcrew.steps.publisher import Publisher
from pitcrew.steps.trigger import Trigger

logger = get_logger(__name__)


@dataclass(frozen=True)
class Accepted:
    """A trigger a Step took: its Run chain, and whether the Step has already finished on it
    (then nothing is redone)."""

    chain: RunChain
    already_finished: bool


class BaseStep(ABC):
    """A Step of the Run chain, one instance per execution on one Run chain.

    The endpoint calls the class's `accept` before answering the trigger (no execution exists
    yet) and the class's `run` in the background after it, which builds the instance and runs
    its `_scenario`. A Step tells only how it finds its Run chain (`_chain_for`) and what it
    does (`_scenario`); the helpers that move and save the chain live here. Whether it has
    finished on the chain the chain itself tells (`RunChain.has_finished`).
    """

    step: ClassVar[Step]

    def __init__(
        self,
        chain: RunChain,
        team_config: TeamConfig,
        db: Repositories,
        deps: StepDependencies,
    ) -> None:
        """
        Args:
            chain: The Run chain this execution works on, loaded in `db`'s session.
            team_config: The config of the chain's Team.
            db: The repositories of this execution's session.
            deps: The clients and the web links the Step works with.
        """
        self.chain = chain
        self.team_config = team_config
        self.db = db
        self.deps = deps

    @classmethod
    def accept(
        cls, trigger: Trigger, team_config: TeamConfig, deps: StepDependencies
    ) -> Accepted:
        """Checks the trigger and records it on its Run chain.

        Args:
            trigger: What finished, as the caller reported it.
            team_config: The config of the trigger's Team.
            deps: The DB and the clients the Step works with.

        Raises:
            StepException: Pitcrew may not handle the trigger: a launch of another pipeline,
                no Run chain, a pipeline that is another kind of Run.
            UnauthorizedException: TestOps rejects Pitcrew's own token.
        """
        check_launch_belongs_to_pipeline(
            deps.testops, cls.step, trigger.allure_launch_id, trigger.pipeline_id
        )
        with Repositories(deps.session_factory) as db:
            chain = cls._chain_for(trigger, team_config, db)
            accepted = Accepted(chain, already_finished=chain.has_finished(cls.step))
        # Also reaches the request log line: the endpoint runs in the request's log scope.
        bind_log_context(trace_id=str(chain.trace_id))
        logger.info("Trigger accepted", already_finished=accepted.already_finished)
        return accepted

    @classmethod
    def run(
        cls, chain_id: int, team_config: TeamConfig, deps: StepDependencies
    ) -> None:
        """The one entry point of a Step: runs it on the Run chain `chain_id`.

        Runs as a background task after the trigger was answered, so it opens its own
        session (the request's one is closed by then) and its own log scope with the Run
        chain's context, then builds the Step for this execution and runs its scenario.

        An error is logged here and goes no further: the caller has its answer already, and
        uvicorn would only print it again without the context. Then the chain is marked
        failed in its current Step, with the reason (`RunChain.record_failure`), which
        `GET /run-chains/{trace_id}` shows; a failed Step counts as not finished, so a
        repeated trigger runs it again from its start.

        Args:
            chain_id: The Run chain `accept` returned.
            team_config: The config of the chain's Team.
            deps: The DB and the clients the Step works with.
        """
        with log_scope(step=cls.step):
            try:
                cls._execute(chain_id, team_config, deps)
            except Exception as error:
                logger.exception("Step failed")
                cls._record_failure(chain_id, error, deps)
                return
            logger.info("Step finished")

    @classmethod
    def _execute(
        cls, chain_id: int, team_config: TeamConfig, deps: StepDependencies
    ) -> None:
        with Repositories(deps.session_factory) as db:
            chain = db.run_chains.get(chain_id)
            bind_log_context(
                trace_id=str(chain.trace_id),
                team=chain.team,
                environment=chain.environment,
            )
            logger.info("Step started")
            cls(chain, team_config, db, deps)._scenario()

    @classmethod
    def _record_failure(
        cls, chain_id: int, error: Exception, deps: StepDependencies
    ) -> None:
        # A fresh session: the Step's one may be unusable after the error (a failed flush
        # or commit), and what it holds unsaved must not be saved with the failure.
        try:
            with Repositories(deps.session_factory) as db:
                chain = db.run_chains.get(chain_id)
                # Masked before `record_failure` cuts it, so that no part of a secret survives.
                chain.record_failure(masked(f"{type(error).__name__}: {error}"))
                db.run_chains.save(chain)
        except Exception:
            logger.exception("Step failure not recorded")

    @classmethod
    @abstractmethod
    def _chain_for(
        cls, trigger: Trigger, team_config: TeamConfig, db: Repositories
    ) -> RunChain:
        """The Run chain of the trigger, recorded or found in `db`. A new chain takes the
        Team's name from `team_config`, never the trigger's spelling of it.

        Raises:
            StepException: The trigger's pipeline is not the Step's kind of Run of any chain.
        """

    @abstractmethod
    def _scenario(self) -> None:
        """What the Step does on its Run chain, as a sequence of named phases."""

    def _doing(self, activity: Activity) -> None:
        """Starts a phase: sets the activity in this Step, saves and binds it to the log."""
        self.chain.set_activity(self.step, activity)
        self._save()
        bind_log_context(activity=activity)
        logger.debug("Activity changed")

    def _record(
        self, run: Run, judgement: Judgement, *, starting_rerun: bool = False
    ) -> None:
        """Records the judgement of the Step's Run (`RunChain.record_judgement`), saves and
        binds the activity the chain moved into."""
        self.chain.record_judgement(
            run, judgement.verdict, starting_rerun=starting_rerun
        )
        self._save()
        bind_log_context(activity=self.chain.activity)

    def _conclude(self, error_groups: list[ErrorGroup] | None = None) -> None:
        """Publishes the Conclusion, then finishes the Step: if Slack fails, the Step stays
        unfinished and a repeated trigger posts it."""
        message = conclusion_message(
            self.chain, error_groups, self.team_config, self.deps.links
        )
        Publisher(self.deps.slack, self.team_config).publish(
            self.chain, PostKind.CONCLUSION, message
        )
        self.chain.record_conclusion()
        self._save()

    def _save(self) -> None:
        self.db.run_chains.save(self.chain)
