from pitcrew.clients.testops import TestResult
from pitcrew.config.team import TeamConfig
from pitcrew.constants import Step
from pitcrew.db.models.run import RunOutcome
from pitcrew.db.models.run_chain import Activity, RunChain
from pitcrew.db.repositories.container import Repositories
from pitcrew.log import bind_log_context, get_logger
from pitcrew.steps.base import BaseStep
from pitcrew.steps.exceptions import PipelineOfAnotherRunException
from pitcrew.steps.judging import judge_run
from pitcrew.steps.trigger import Trigger

logger = get_logger(__name__)


class NightRunStep(BaseStep):
    """The `night_run` Step: the Nightly run has finished. Its trigger starts the Run chain."""

    step = Step.NIGHT_RUN

    @classmethod
    def _chain_for(
        cls, trigger: Trigger, team_config: TeamConfig, db: Repositories
    ) -> RunChain:
        """The Run chain of the trigger's pipeline as its Nightly run, a new one the first
        time, of the Team as its config spells it."""
        chain = db.run_chains.get_or_create_for_nightly_run(
            team=team_config.name,
            environment=trigger.environment,
            nightly_pipeline_id=trigger.pipeline_id,
            nightly_launch_id=trigger.allure_launch_id,
        )
        if chain.nightly_run.pipeline_id != trigger.pipeline_id:
            raise PipelineOfAnotherRunException(
                cls.step,
                f"Pipeline {trigger.pipeline_id} is the Rerun of Run chain "
                f"{chain.trace_id}, not a Nightly run",
                pipeline_id=trigger.pipeline_id,
                launch_id=trigger.allure_launch_id,
            )
        return chain

    @property
    def nightly_launch_id(self) -> int:
        launch_id = self.chain.nightly_run.launch_id
        assert launch_id is not None, "came with the night_run trigger"
        return launch_id

    def _scenario(self) -> None:
        """Judges the Nightly run (`judge_run`). Broken (its pipeline stopped before the
        tests finished, far too few results, or far too many failures): a Conclusion says why,
        nothing is rerun. *With failures*: when the Team has the `rerun` feature, a Rerun of
        the Failed tests is started (ADR 0002). The judgement is recorded before GitLab is
        called, so that a Step failing on the way leaves it recorded."""
        nightly_run = self.chain.nightly_run
        self._doing(Activity.JUDGING_RUN)
        judgement = judge_run(nightly_run, self.team_config, self.deps)
        if judgement.outcome == RunOutcome.BROKEN:
            self._record(nightly_run, judgement)
            self._conclude()
        elif judgement.outcome == RunOutcome.WITH_FAILURES:
            assert judgement.failed_tests is not None, "read to find the failures"
            test_case_ids = self._rerun_test_case_ids(judgement.failed_tests)
            self._record(nightly_run, judgement, starting_rerun=bool(test_case_ids))
            if test_case_ids:
                self._rerun(test_case_ids)
        else:
            self._record(nightly_run, judgement)

    def _rerun_test_case_ids(self, failed_tests: list[TestResult]) -> set[int]:
        """The test cases of the Failed tests to rerun; none when the Team has no Rerun or
        the chain has its Rerun already (a resumed Step does not start a second one)."""
        if not self.team_config.features.rerun or self.chain.rerun is not None:
            return set()
        test_case_ids = {
            test.test_case_id for test in failed_tests if test.test_case_id is not None
        }
        if not test_case_ids:
            # An empty plan would not narrow the Rerun down to anything.
            logger.warning(
                "No Rerun: no Failed test has a test case",
                failed_count=len(failed_tests),
            )
        return test_case_ids

    def _rerun(self, test_case_ids: set[int]) -> None:
        rerun_pipeline_id = self._start_rerun(test_case_ids)
        logger.info(
            "Rerun started",
            rerun_pipeline_id=rerun_pipeline_id,
            test_case_count=len(test_case_ids),
        )
        self.chain.start_rerun(rerun_pipeline_id, len(test_case_ids))
        self._save()
        bind_log_context(activity=self.chain.activity)

    def _start_rerun(self, test_case_ids: set[int]) -> int:
        """Writes the Failed tests' test cases into the Team's Rerun test plan and creates a
        pipeline of the test repo that runs only that plan on the Nightly run's Environment.
        Returns the Rerun pipeline id."""
        chain, team_config = self.chain, self.team_config
        rerun_test_plan_id = team_config.allure.rerun_test_plan_id
        self.deps.testops.replace_test_plan_test_cases(
            rerun_test_plan_id, test_case_ids
        )
        branch = team_config.rerun.branch
        # `IS_NIGHTLY` is never set: the test repo would treat the Rerun as a Nightly run.
        return self.deps.gitlab.create_pipeline(
            team_config.gitlab.project_path,
            branch=branch,
            inputs=team_config.rerun.pipeline_inputs
            | {
                "PROJECT_NAME": chain.team,
                "ENVIRONMENT": chain.environment,
                "TEST_PLAN_ID": str(rerun_test_plan_id),
            },
            variables={
                "PITCREW_STEP": Step.NIGHT_RERUN,
                # The test repo's own tags, so its launch filters still find the Rerun.
                "ALLURE_LAUNCH_TAGS": (
                    f"{branch}, gitlab, pitcrew-rerun-of-{self.nightly_launch_id}"
                ),
            },
        )
