from pitcrew.constants import Step


class StepException(Exception):
    """Base of the errors a Step raises about the trigger it was given.

    `reason` is the human-readable why, fit to show the caller; `details` are the facts behind
    it (ids, what was found) for the logs. `str()` gives all three:
    `Step night_run: <reason> (launch_id=276357, pipeline_id=478951)`.
    """

    def __init__(self, step: Step, reason: str, **details: object) -> None:
        """
        Args:
            step: The Step the trigger was for.
            reason: Why, fit to show the caller.
            **details: The facts behind it, for the logs.
        """
        self.step = step
        self.reason = reason
        self.details = details
        facts = ", ".join(f"{name}={value}" for name, value in details.items())
        super().__init__(f"Step {step}: {reason}" + (f" ({facts})" if facts else ""))


class LaunchRejectedException(StepException):
    """The trigger's Allure launch is not one Pitcrew may handle for the trigger's pipeline."""


class UnknownRunChainException(StepException):
    """No Run chain is waiting for the trigger's pipeline."""


class PipelineOfAnotherRunException(StepException):
    """The trigger's pipeline is already a Run of another kind than the Step's: a pipeline
    belongs to one Run."""


class StepNotImplementedException(Exception):
    """A Step of the Run chain that Pitcrew has no class for yet.

    `str()` is the reason, fit to show the caller: `Step night_run is not implemented yet`.

    Attributes:
        step: The Step the trigger was for.
    """

    def __init__(self, step: Step) -> None:
        """
        Args:
            step: The Step the trigger was for.
        """
        super().__init__(f"Step {step} is not implemented yet")
        self.step = step
