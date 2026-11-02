from pydantic import BaseModel

from pitcrew.constants import Environment, Step


class Trigger(BaseModel):
    """A Step of a Team's Run chain has finished on an Environment: what the Steps are given,
    whatever brought it (the HTTP body `api.schemas.TriggerRequest` extends it).

    Attributes:
        team: The Team as the caller spelled it, any Team with a Team config; a Step uses
            the config's `name`, the spelling `qa_automation` takes, never this one.
    """

    environment: Environment
    team: str
    pipeline_id: int
    step: Step
    allure_launch_id: int
