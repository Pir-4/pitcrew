from pitcrew.constants import Step
from pitcrew.steps.base import BaseStep
from pitcrew.steps.exceptions import StepNotImplementedException
from pitcrew.steps.night_rerun import NightRerunStep
from pitcrew.steps.night_run import NightRunStep

STEPS: dict[Step, type[BaseStep]] = {
    Step.NIGHT_RUN: NightRunStep,
    Step.NIGHT_RERUN: NightRerunStep,
}


def step_class(step: Step) -> type[BaseStep]:
    """The class of a Step, from `STEPS`.

    Args:
        step: The Step of the trigger.

    Raises:
        StepNotImplementedException: `STEPS` has no class for the Step.
    """
    found = STEPS.get(step)
    if found is None:
        raise StepNotImplementedException(step)
    return found
