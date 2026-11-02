import json
import re
from dataclasses import dataclass
from typing import Any

import httpx2 as httpx

from tests.support.constants import (
    ALLURE_PROJECT,
    ALLURE_TOKEN,
    GITLAB_TOKEN,
    QA_AUTOMATION,
    SLACK_WEBHOOK,
)
from tests.support.scenarios import Night


class FakeTestOps:
    """Allure TestOps behind an `httpx` transport: answers from the night it serves (see
    `serve`) and what the night does not hold the way TestOps does; keeps the test plans
    written to it and what was read of the night's launches."""

    FAILED_RQL = re.compile(r'launch = (\d+) and status in \["failed", "broken"\]')
    ALL_RQL = re.compile(r"launch = (\d+)")

    def __init__(self) -> None:
        self.night: Night | None = None
        # The test plans written, as `(test_plan_id, body)`, once per write.
        self.written_test_plans: list[tuple[int, Any]] = []
        # The launches whose pipeline was asked for, once per request.
        self.checked_launches: list[int] = []
        # The launches whose results were searched, once per search.
        self.searched_launches: list[int] = []
        # The test results whose error was read, once per read.
        self.read_test_results: list[int] = []
        # Launches answered `404`; the real TestOps answers a missing launch `403`.
        self.not_found_launches: set[int] = set()
        # Every request answered as one with a revoked token, when set.
        self.token_revoked = False
        self.transport = httpx.MockTransport(self.handle)

    def serve(self, night: Night) -> None:
        self.night = night

    def handle(self, request: httpx.Request) -> httpx.Response:
        token = request.headers.get("Authorization")
        if self.token_revoked or token != f"Api-Token {ALLURE_TOKEN}":
            return httpx.Response(401, json={"message": "auth.bad-token"})
        path = request.url.path
        if match := re.fullmatch(r"/api/rs/launch/(\d+)/job", path):
            self.checked_launches.append(int(match[1]))
            if int(match[1]) in self.not_found_launches:
                return httpx.Response(404, json={"message": "Not Found"})
            return self.of_launch(int(match[1]), "launch_job_runs.json")
        if match := re.fullmatch(r"/api/rs/testplan/(\d+)", path):
            # The night's test plans: the nightly one read, the Rerun one written; both
            # answer the plan as TestOps holds it.
            plan = self.recorded("test_plan_id", int(match[1]), "test_plan.json")
            if plan is not None and request.method == "PATCH":
                self.written_test_plans.append(
                    (int(match[1]), json.loads(request.content))
                )
            return recorded_or_missing(plan)
        if match := re.fullmatch(r"/api/rs/testresult/(\d+)", path):
            self.read_test_results.append(int(match[1]))
            body = (
                self.night.recorded_test_result(int(match[1])) if self.night else None
            )
            if body is None:
                return httpx.Response(404, json={"message": "Not Found"})
            return httpx.Response(200, json=body)
        if path == "/api/rs/testresult/__search":
            params = request.url.params
            if params.get("projectId") != str(ALLURE_PROJECT):
                return httpx.Response(400, json={"message": "invalid query"})
            rql, page = params.get("rql", ""), params.get("page", "0")
            if match := self.FAILED_RQL.fullmatch(rql):
                self.searched_launches.append(int(match[1]))
                return self.of_launch(int(match[1]), f"failed_tests_page{page}.json")
            if (match := self.ALL_RQL.fullmatch(rql)) and params.get("size") == "1":
                self.searched_launches.append(int(match[1]))
                return self.of_launch(int(match[1]), "result_count.json")
            return httpx.Response(400, json={"message": "invalid query"})
        return httpx.Response(404)

    def of_launch(self, launch_id: int, name: str) -> httpx.Response:
        return recorded_or_missing(self.recorded("launch_id", launch_id, name))

    def recorded(self, role: str, id_: int, name: str) -> Any | None:
        return self.night.recorded_of(role, id_, name) if self.night else None


@dataclass(frozen=True)
class CreatedPipeline:
    """A pipeline GitLab created: its branch, its `spec:inputs` and its variables."""

    ref: str
    inputs: dict[str, Any]
    variables: dict[str, str]


class FakeGitLab:
    """GitLab behind an `httpx` transport: answers the jobs of the pipelines of the night it
    serves (see `serve`) and creates the night's Rerun pipeline, keeping what it created."""

    def __init__(self) -> None:
        self.night: Night | None = None
        self.created_pipelines: list[CreatedPipeline] = []
        # What reading the jobs of a pipeline answers instead of the night's, when set.
        self.pipeline_jobs_error: httpx.Response | None = None
        # What creating a pipeline answers instead of the night's Rerun, when set.
        self.create_pipeline_error: httpx.Response | None = None
        self.transport = httpx.MockTransport(self.handle)

    def serve(self, night: Night) -> None:
        self.night = night

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("PRIVATE-TOKEN") != GITLAB_TOKEN:
            return httpx.Response(401, json={"message": "401 Unauthorized"})
        jobs = re.fullmatch(
            rf"/api/v4/projects/{QA_AUTOMATION}/pipelines/(\d+)/jobs",
            request.url.raw_path.decode().split("?")[0],
        )
        if request.method == "GET" and jobs:
            if self.pipeline_jobs_error is not None:
                return self.pipeline_jobs_error
            body = (
                self.night.recorded_of(
                    "pipeline_id", int(jobs[1]), "pipeline_jobs.json"
                )
                if self.night
                else None
            )
            if body is None:
                return httpx.Response(404, json={"message": "404 Not found"})
            return httpx.Response(200, json=body)
        if (
            request.method == "POST"
            and request.url.raw_path
            == f"/api/v4/projects/{QA_AUTOMATION}/pipeline".encode()
        ):
            if self.create_pipeline_error is not None:
                return self.create_pipeline_error
            rerun = self.night.recorded_rerun if self.night else None
            if (body := rerun.recorded("pipeline.json") if rerun else None) is None:
                raise LookupError("The night records no Rerun pipeline to create")
            self.created_pipelines.append(created_pipeline(json.loads(request.content)))
            return httpx.Response(201, json=body)
        return httpx.Response(404, json={"message": "404 Project Not Found"})


def created_pipeline(body: dict[str, Any]) -> CreatedPipeline:
    """What a body of `POST .../pipeline` asks GitLab to create."""
    return CreatedPipeline(
        ref=body["ref"],
        inputs=body.get("inputs", {}),
        variables={
            variable["key"]: variable["value"] for variable in body.get("variables", [])
        },
    )


class FakeSlack:
    """Slack incoming webhooks behind an `httpx` transport: answers `ok` the way Slack does and
    keeps what was posted. `failures` makes the next posts answer `500`."""

    def __init__(self) -> None:
        # The bodies of the posts Slack accepted.
        self.posted: list[Any] = []
        self.failures = 0
        self.transport = httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        if str(request.url) != SLACK_WEBHOOK:
            return httpx.Response(404, text="no_service")
        if self.failures:
            self.failures -= 1
            return httpx.Response(500, text="rollup_error")
        self.posted.append(json.loads(request.content))
        return httpx.Response(200, text="ok")


def recorded_or_missing(body: Any | None) -> httpx.Response:
    """A recorded answer of TestOps or, when the night holds none, what TestOps answers for a
    launch that does not exist."""
    if body is None:
        return httpx.Response(403, json={"message": "Forbidden"})
    return httpx.Response(200, json=body)
