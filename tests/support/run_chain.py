from dataclasses import dataclass
from typing import Any, Protocol

import httpx2 as httpx
from fastapi.testclient import TestClient

from tests.support.constants import AUTH, TOKEN
from tests.support.scenarios import Night


@dataclass(frozen=True)
class Answer:
    """What Pitcrew answered a trigger."""

    status_code: int
    body: dict[str, Any]
    # The id of the request, as the `X-Request-Id` header gives it.
    request_id: str

    @classmethod
    def of(cls, response: httpx.Response) -> "Answer":
        return cls(
            response.status_code, response.json(), response.headers["X-Request-Id"]
        )

    @property
    def trace_id(self) -> str:
        """The trace id of the Run chain the trigger belongs to."""
        return self.body["trace_id"]

    @property
    def detail(self) -> Any:
        """Why the trigger was rejected."""
        return self.body["detail"]

    @property
    def reason(self) -> str:
        """Why the trigger was rejected, as one line: the detail, or for a body that failed
        validation each field it names with its message (`environment: Input should be ...`)."""
        if isinstance(self.detail, str):
            return self.detail
        return "; ".join(f"{error['loc'][-1]}: {error['msg']}" for error in self.detail)


class Pitcrew:
    """The service, driven through the Run chain: triggers its Steps for a night and reads the
    Run chain back. It sends the bearer token (`token` another one, `None` none) and builds the
    trigger bodies; `http` is the raw `TestClient`, for the tests of HTTP itself."""

    def __init__(self, http: TestClient) -> None:
        self.http = http

    def trigger_night_run(
        self, night: Night, *, token: str | None = TOKEN, **overrides: object
    ) -> Answer:
        """Triggers the `night_run` Step for the night's Nightly run; `overrides` replace
        fields of the trigger."""
        return self.trigger(night_run_body(night, **overrides), token)

    def trigger_night_rerun(
        self, night: Night, *, token: str | None = TOKEN, **overrides: object
    ) -> Answer:
        """Triggers the `night_rerun` Step for the night's Rerun; `overrides` replace fields
        of the trigger."""
        return self.trigger(night_rerun_body(night, **overrides), token)

    def trigger(self, body: dict[str, object], token: str | None = TOKEN) -> Answer:
        headers = {} if token is None else {"Authorization": f"Bearer {token}"}
        return Answer.of(self.http.post("/triggers", json=body, headers=headers))

    def run_chain(self, trace_id: str) -> dict[str, Any]:
        """The Run chain of the trace id, as `GET /run-chains/{trace_id}` shows it."""
        response = self.http.get(f"/run-chains/{trace_id}", headers=AUTH)
        response.raise_for_status()
        return response.json()


class StartPitcrew(Protocol):
    """The type of the `start_pitcrew` fixture: starts the service with a Team config variant
    of `data/team_configs/`, named without `.yaml`, as the config of the Team."""

    def __call__(self, config: str = "gateway", team: str = "Gateway") -> Pitcrew: ...


def night_run_body(night: Night, **overrides: object) -> dict[str, object]:
    """The body of the `night_run` trigger of the night's Nightly run."""
    return {
        "environment": "staging",
        "team": "Gateway",
        "pipeline_id": night.nightly.pipeline_id,
        "step": "night_run",
        "allure_launch_id": night.nightly.launch_id,
    } | overrides


def night_rerun_body(night: Night, **overrides: object) -> dict[str, object]:
    """The body of the `night_rerun` trigger of the night's Rerun."""
    return (
        night_run_body(
            night,
            step="night_rerun",
            pipeline_id=night.rerun.pipeline_id,
            allure_launch_id=night.rerun.launch_id,
        )
        | overrides
    )
