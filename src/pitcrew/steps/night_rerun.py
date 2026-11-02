from pitcrew.clients.testops import TestResult
from pitcrew.config.team import TeamConfig
from pitcrew.constants import Step
from pitcrew.db.models.error_group import ErrorGroup
from pitcrew.db.models.run import Run, RunOutcome
from pitcrew.db.models.run_chain import Activity, RunChain
from pitcrew.db.repositories.container import Repositories
from pitcrew.log import get_logger
from pitcrew.steps.base import BaseStep
from pitcrew.steps.error_groups import recognize_error_groups
from pitcrew.steps.exceptions import UnknownRunChainException
from pitcrew.steps.judging import judge_run
from pitcrew.steps.trigger import Trigger

logger = get_logger(__name__)


class NightRerunStep(BaseStep):
    """The `night_rerun` Step: the Rerun has finished. Its trigger ends the Run chain with the
    Conclusion."""

    step = Step.NIGHT_RERUN

    @classmethod
    def _chain_for(
        cls, trigger: Trigger, team_config: TeamConfig, db: Repositories
    ) -> RunChain:
        """The Run chain that started the trigger's pipeline as its Rerun; the Rerun launch is
        recorded on it."""
        chain = db.run_chains.get_by_pipeline(trigger.pipeline_id)
        if (
            chain is None
            or chain.rerun is None
            or chain.rerun.pipeline_id != trigger.pipeline_id
        ):
            raise UnknownRunChainException(
                cls.step,
                f"Pipeline {trigger.pipeline_id} is not the Rerun of any Run chain",
                pipeline_id=trigger.pipeline_id,
                launch_id=trigger.allure_launch_id,
            )
        if not chain.has_finished(cls.step):
            chain.accept_rerun_launch(trigger.allure_launch_id)
            db.run_chains.save(chain)
        return chain

    @property
    def rerun(self) -> Run:
        rerun = self.chain.rerun
        assert rerun is not None, "the chain was found by it"
        return rerun

    def _scenario(self) -> None:
        """Judges the Rerun (`judge_run`): by the rules of the Nightly run, against the test
        cases written into the Rerun test plan and without the share of failures (the Rerun
        runs only Failed tests). A Rerun that is not broken has its Error groups recognized,
        when the Team has them. Then posts the Conclusion: broken and why, or how many tests
        still fail and the Error groups among them."""
        self._doing(Activity.JUDGING_RUN)
        judgement = judge_run(self.rerun, self.team_config, self.deps)
        error_groups = None
        if judgement.outcome != RunOutcome.BROKEN:
            assert judgement.failed_tests is not None, "read to check the results"
            if self.team_config.features.error_groups:
                self._doing(Activity.RECOGNIZING_ERROR_GROUPS)
                error_groups = self._recognize_error_groups(judgement.failed_tests)
        self._record(self.rerun, judgement)
        self._conclude(error_groups)

    def _recognize_error_groups(
        self, failed_tests: list[TestResult]
    ) -> list[ErrorGroup]:
        """Reads the error of every Failed test of the Rerun and stores the Error groups among
        them. A resumed Step takes the ones it stored before, without reading the errors
        again."""
        groups = self.db.error_groups.for_chain(self.chain.id)
        if not groups:
            groups = self.db.error_group_service.record_for_chain(
                self.chain.id,
                recognize_error_groups(
                    (test, self.deps.testops.test_result_message(test.result_id))
                    for test in failed_tests
                ),
            )
        logger.info(
            "Error groups recognized",
            error_group_count=len(groups),
            grouped_test_count=sum(group.test_count for group in groups),
        )
        return groups
