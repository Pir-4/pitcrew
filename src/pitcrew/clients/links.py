"""Links to the web pages of GitLab and TestOps, built from the settings without a request."""

import base64
import json
from collections.abc import Iterable
from urllib.parse import quote

from pitcrew.config.settings import Settings


class WebLinks:
    """The one place that builds a web page link; the clients only talk to their APIs."""

    def __init__(self, settings: Settings) -> None:
        """
        Args:
            settings: The service settings: the GitLab URL and the TestOps endpoint.
        """
        self._gitlab_url = str(settings.gitlab.url).rstrip("/")
        self._testops_url = str(settings.allure.endpoint).rstrip("/")

    def pipeline(self, project_path: str, pipeline_id: int) -> str:
        """The page of the pipeline in GitLab.

        Args:
            project_path: The project, e.g. `gateway/qa_automation`.
            pipeline_id: The pipeline.
        """
        return f"{self._gitlab_url}/{project_path}/-/pipelines/{pipeline_id}"

    def launch(self, launch_id: int) -> str:
        """The page of the launch in TestOps.

        Args:
            launch_id: The launch.
        """
        return f"{self._testops_url}/launch/{launch_id}"

    def test_result(self, launch_id: int, result_id: int) -> str:
        """The page of a test result, in the tree of its launch.

        Args:
            launch_id: The launch that holds the result.
            result_id: The test result.
        """
        return f"{self._testops_url}/launch/{launch_id}/tree/{result_id}"

    def test_cases(self, project_id: int, test_case_ids: Iterable[int]) -> str:
        """The test cases page of the project showing exactly these test cases: its search
        holds an AQL filter by id, as JSON in base64, URL-encoded.

        Args:
            project_id: The TestOps project.
            test_case_ids: The test cases to show.
        """
        ids = ", ".join(str(test_case_id) for test_case_id in sorted(test_case_ids))
        search = json.dumps(
            [{"id": "aql", "type": "string", "value": f"id in [{ids}]"}],
            separators=(",", ":"),
        )
        encoded = quote(base64.b64encode(search.encode()).decode(), safe="")
        return f"{self._testops_url}/project/{project_id}/test-cases?search={encoded}"
