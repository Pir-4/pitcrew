"""GitLab through its REST API (`/api/v4`); only the calls Pitcrew needs."""

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import quote

import httpx2 as httpx

from pitcrew.clients.base import BaseClient
from pitcrew.config.settings import GitLabSettings

type InputValue = str | int | bool
"""The value of a `spec:inputs` input of a pipeline."""


@dataclass(frozen=True)
class Job:
    """A job of a pipeline, in its latest attempt.

    Attributes:
        status: GitLab's job status: `success`, `failed`, `canceled`, `skipped`, `manual`, ...
        allow_failure: A failure of the job does not fail the pipeline.
    """

    id: int
    name: str
    stage: str
    status: str
    allow_failure: bool


class GitLabClient(BaseClient):
    # GitLab's maximum page size: no pagination, a pipeline of the test repo has far fewer jobs.
    PAGE_SIZE = 100

    def __init__(
        self, settings: GitLabSettings, transport: httpx.BaseTransport | None = None
    ) -> None:
        """
        Args:
            settings: The GitLab URL and token.
            transport: A faked transport serving recorded responses, for the tests.
        """
        super().__init__(
            base_url=f"{str(settings.url).rstrip('/')}/api/v4",
            headers={"PRIVATE-TOKEN": settings.token.get_secret_value()},
            transport=transport,
        )

    def pipeline_jobs(self, project_path: str, pipeline_id: int) -> list[Job]:
        """The jobs of a pipeline; a retried job only in its latest attempt.

        Args:
            project_path: The project, e.g. `gateway/qa_automation`.
            pipeline_id: The pipeline.
        """
        return [
            Job(
                id=job["id"],
                name=job["name"],
                stage=job["stage"],
                status=job["status"],
                allow_failure=job["allow_failure"],
            )
            for job in self._get(
                f"/projects/{quote(project_path, safe='')}/pipelines/{pipeline_id}/jobs",
                params={"per_page": self.PAGE_SIZE},
            )
        ]

    def create_pipeline(
        self,
        project_path: str,
        branch: str,
        inputs: Mapping[str, InputValue],
        variables: Mapping[str, str],
    ) -> int:
        """Creates a pipeline of the project.

        Args:
            project_path: The project, e.g. `gateway/qa_automation`.
            branch: The branch the pipeline runs on.
            inputs: Fill the `spec:inputs` of its `.gitlab-ci.yml`, read there as
                `$[[ inputs.NAME ]]`; a variable of the same name would not reach them.
            variables: Become pipeline variables.

        Returns:
            The id of the new pipeline.
        """
        pipeline = self._post(
            f"/projects/{quote(project_path, safe='')}/pipeline",
            json={
                "ref": branch,
                "inputs": dict(inputs),
                "variables": [
                    {"key": key, "value": value} for key, value in variables.items()
                ],
            },
        )
        return pipeline["id"]
