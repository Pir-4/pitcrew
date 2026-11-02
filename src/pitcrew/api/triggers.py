from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status

from pitcrew.api.auth import require_trigger_token
from pitcrew.api.dependencies import get_step_dependencies, get_team_configs
from pitcrew.api.schemas import TriggerRequest, TriggerResponse
from pitcrew.config.team import TeamConfigs
from pitcrew.log import bind_log_context
from pitcrew.steps.dependencies import StepDependencies
from pitcrew.steps.registry import step_class

router = APIRouter()


@router.post(
    "/triggers",
    dependencies=[Depends(require_trigger_token)],
    status_code=status.HTTP_202_ACCEPTED,
    response_description="Accepted, the Step runs in the background",
    # Documentation only: the 200 is set at runtime, so OpenAPI does not know it otherwise.
    responses={
        status.HTTP_200_OK: {
            "model": TriggerResponse,
            "description": "The Step has already finished, nothing is redone",
        },
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or wrong bearer token"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Unknown Team or Step, a launch of another pipeline, or a "
            "Rerun pipeline of no Run chain"
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "TestOps rejected Pitcrew's own token"
        },
        status.HTTP_501_NOT_IMPLEMENTED: {
            "description": "The Step is not implemented yet"
        },
    },
)
def receive_trigger(
    trigger: TriggerRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    team_configs: Annotated[TeamConfigs, Depends(get_team_configs)],
    deps: Annotated[StepDependencies, Depends(get_step_dependencies)],
) -> TriggerResponse:
    """Receives a trigger from the Run chain: a Step of a Team's pipeline has finished.

    Answers with the trace id of the trigger's Run chain, the same for every trigger of the
    chain: `202` when the Step runs in the background, `200` when it has already finished and
    nothing is redone; an unfinished one is resumed. The chain is followed through
    `GET /run-chains/{trace_id}`.
    """
    bind_log_context(
        step=trigger.step,
        team=trigger.team,
        environment=trigger.environment,
        pipeline_id=trigger.pipeline_id,
        launch_id=trigger.allure_launch_id,
    )
    team_config = team_configs.get(trigger.team)
    step = step_class(trigger.step)
    accepted = step.accept(trigger, team_config, deps)

    if accepted.already_finished:
        response.status_code = status.HTTP_200_OK
    else:
        background_tasks.add_task(step.run, accepted.chain.id, team_config, deps)
    return TriggerResponse(trace_id=accepted.chain.trace_id)
