"""Domain constants shared by the API, the clients and the Steps."""

from enum import StrEnum


class Step(StrEnum):
    """The stage of the Run chain a trigger comes from (`CONTEXT.md`), in the order the chain
    goes through them: `RunChain.has_finished` tells a Step behind the current one by it."""

    NIGHT_RUN = "night_run"
    NIGHT_RERUN = "night_rerun"


class Environment(StrEnum):
    """The stand the tests run against, as the `ENVIRONMENT` input of `qa_automation` lists
    it: the Rerun runs on the Environment of its Nightly run."""

    STAGING = "staging"
    TESTNET = "testnet"


class JobStatus(StrEnum):
    """Status of a GitLab job; only the ones Pitcrew tells apart."""

    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"


class TestStatus(StrEnum):
    """Status of a test result in Allure."""

    __test__ = False  # Not a pytest test class despite the name.

    PASSED = "passed"
    FAILED = "failed"
    BROKEN = "broken"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"


# A tuple, not a set: the query built from it keeps one order.
FAILED_STATUSES = (TestStatus.FAILED, TestStatus.BROKEN)


class ModelTier(StrEnum):
    """How strong a model an Agent task needs (`CONTEXT.md`): each tier is one model of the
    LiteLLM pool, named in the service env (`AGENT_MODEL_<TIER>`)."""

    JUNIOR = "junior"
    MIDDLE = "middle"
    SENIOR = "senior"
