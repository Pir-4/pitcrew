"""Checks of a trigger shared by the Steps. They run before the trigger is answered, so that a
rejected one gets `422` and nothing is recorded."""

from pitcrew.clients.exceptions import AccessDeniedException, NotFoundException
from pitcrew.clients.testops import TestOpsClient
from pitcrew.constants import Step
from pitcrew.steps.exceptions import LaunchRejectedException


def check_launch_belongs_to_pipeline(
    testops: TestOpsClient, step: Step, launch_id: int, pipeline_id: int
) -> None:
    """The precondition of every Step, checked before the trigger is answered: the pipeline
    reported into the launch, so that Pitcrew never handles the tests of another pipeline.

    Args:
        testops: Where the launch is read.
        step: The Step the trigger is for, named in the rejection.
        launch_id: The trigger's Allure launch.
        pipeline_id: The trigger's pipeline.

    Raises:
        LaunchRejectedException: The launch is not the pipeline's, with the reason.
        UnauthorizedException: TestOps rejects Pitcrew's own token; not the trigger's fault.
    """
    ids = {"launch_id": launch_id, "pipeline_id": pipeline_id}
    try:
        pipeline_ids = testops.launch_pipeline_ids(launch_id)
    except AccessDeniedException as error:
        raise LaunchRejectedException(
            step,
            f"TestOps denies access to Allure launch {launch_id}: it does not exist, "
            "or the token has no access to its project",
            **ids,
            testops=str(error),
        ) from error
    except NotFoundException as error:
        raise LaunchRejectedException(
            step,
            f"Allure launch {launch_id} does not exist in TestOps",
            **ids,
            testops=str(error),
        ) from error
    if not pipeline_ids:
        raise LaunchRejectedException(
            step, f"Allure launch {launch_id} has no GitLab pipeline", **ids
        )
    if pipeline_id not in pipeline_ids:
        pipelines = ", ".join(str(other) for other in sorted(pipeline_ids))
        raise LaunchRejectedException(
            step,
            f"Allure launch {launch_id} belongs to pipeline {pipelines}, "
            f"not to pipeline {pipeline_id}",
            **ids,
            launch_pipeline_ids=sorted(pipeline_ids),
        )
