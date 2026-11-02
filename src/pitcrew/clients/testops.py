"""Allure TestOps through its REST API; only the calls Pitcrew needs.

Endpoints as in the TestOps Swagger (`/api-docs/rs`); `/api/rs/...` is the same API under the
prefix `qa_automation` uses.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import httpx2 as httpx

from pitcrew.clients.base import BaseClient
from pitcrew.config.settings import AllureSettings
from pitcrew.constants import TestStatus


@dataclass(frozen=True)
class TestResult:
    __test__ = False  # Not a pytest test class despite the name.

    result_id: int
    test_case_id: int | None
    name: str
    status: TestStatus


class TestOpsClient(BaseClient):
    __test__ = False  # Not a pytest test class despite the name.

    PAGE_SIZE = 500

    def __init__(
        self, settings: AllureSettings, transport: httpx.BaseTransport | None = None
    ) -> None:
        """
        Args:
            settings: The TestOps URL and token.
            transport: A faked transport serving recorded responses, for the tests.
        """
        super().__init__(
            base_url=f"{str(settings.endpoint).rstrip('/')}/api/rs",
            headers={"Authorization": f"Api-Token {settings.token.get_secret_value()}"},
            transport=transport,
        )

    def launch_pipeline_ids(self, launch_id: int) -> set[int]:
        """The GitLab pipelines that reported into a launch (its job runs' `externalId`).

        Args:
            launch_id: The launch.

        Raises:
            AccessDeniedException: The launch does not exist; TestOps answers it `403`.
        """
        return {
            int(job_run["externalId"])
            for job_run in self._get(f"/launch/{launch_id}/job")
            if str(job_run.get("externalId", "")).isdigit()
        }

    def test_results(
        self, project_id: int, launch_id: int, statuses: Sequence[TestStatus]
    ) -> list[TestResult]:
        """The launch's results with one of `statuses`, every page of them: the first page
        says how many there are.

        Args:
            project_id: The TestOps project of the launch.
            launch_id: The launch.
            statuses: The statuses of the results to read.
        """
        status_list = ", ".join(f'"{status}"' for status in statuses)
        rql = f"launch = {launch_id} and status in [{status_list}]"
        first = self._search_results(project_id, rql, page=0)
        pages = [first] + [
            self._search_results(project_id, rql, page)
            for page in range(1, first["totalPages"])
        ]
        return [
            TestResult(
                result_id=result["id"],
                test_case_id=result.get("testCaseId"),
                name=result["name"],
                status=TestStatus(result["status"]),
            )
            for body in pages
            for result in body["content"]
        ]

    def test_result_message(self, result_id: int) -> str | None:
        """The error of a test result as Allure shows it on top (`message`).

        Args:
            result_id: The test result.

        Returns:
            The error, or `None` for a result without one.
        """
        return self._get(f"/testresult/{result_id}").get("message")

    def result_count(self, project_id: int, launch_id: int) -> int:
        """How many results the launch holds, of every status.

        Args:
            project_id: The TestOps project of the launch.
            launch_id: The launch.
        """
        page = self._search_results(project_id, f"launch = {launch_id}", page=0, size=1)
        return page["totalElements"]

    def test_plan_test_case_count(self, test_plan_id: int) -> int:
        """How many test cases the test plan holds now.

        Args:
            test_plan_id: The test plan.
        """
        return self._get(f"/testplan/{test_plan_id}")["testCasesCount"]

    def replace_test_plan_test_cases(
        self, test_plan_id: int, test_case_ids: Iterable[int]
    ) -> None:
        """Makes the test plan hold exactly these test cases, at once (no sync needed): its
        query selects them by id, and the whole tree under the query is selected.

        Args:
            test_plan_id: The test plan.
            test_case_ids: The test cases it holds from now on.
        """
        ids = ", ".join(str(test_case_id) for test_case_id in sorted(test_case_ids))
        self._patch(
            f"/testplan/{test_plan_id}",
            json={
                "baseRql": f"id in [{ids}]",
                # Inverted with nothing excluded: every test case the query finds.
                "treeSelection": {
                    "inverted": True,
                    "groupsInclude": [],
                    "groupsExclude": [],
                    "leafsInclude": [],
                    "leafsExclude": [],
                },
            },
        )

    def _search_results(
        self,
        project_id: int,
        rql: str,
        page: int,
        size: int = PAGE_SIZE,
        sort: str = "id,ASC",
    ) -> Any:
        """One page of `GET /testresult/__search`. `sort` must give a stable order, or the
        pages may overlap or skip results."""
        return self._get(
            "/testresult/__search",
            params={
                "projectId": project_id,
                "rql": rql,
                "page": page,
                "size": size,
                "sort": sort,
            },
        )
