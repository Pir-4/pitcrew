from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pitcrew.api.dependencies import get_gitlab, get_testops
from pitcrew.clients.gitlab import GitLabClient
from pitcrew.clients.testops import TestOpsClient
from pitcrew.config.settings import get_settings
from pitcrew.main import app
from tests.support.config import use_team_config
from tests.support.fakes import FakeGitLab, FakeSlack, FakeTestOps
from tests.support.run_chain import Pitcrew, StartPitcrew
from tests.support.scenarios import LoadScenario, Night


@pytest.fixture
def testops(service_env: dict[str, str]) -> Iterator[FakeTestOps]:
    fake = FakeTestOps()
    client = TestOpsClient(get_settings().allure, transport=fake.transport)
    app.dependency_overrides[get_testops] = lambda: client
    yield fake
    app.dependency_overrides.pop(get_testops)
    client.close()


@pytest.fixture
def gitlab(service_env: dict[str, str]) -> Iterator[FakeGitLab]:
    fake = FakeGitLab()
    client = GitLabClient(get_settings().gitlab, transport=fake.transport)
    app.dependency_overrides[get_gitlab] = lambda: client
    yield fake
    app.dependency_overrides.pop(get_gitlab)
    client.close()


@pytest.fixture
def start_pitcrew(
    service_env: dict[str, str],
    testops: FakeTestOps,
    gitlab: FakeGitLab,
    slack: FakeSlack,
) -> Iterator[StartPitcrew]:
    """Starts the service with the fakes in place and a Team config variant of
    `data/team_configs/` as the config of a Team, Gateway by default; gives its driver,
    the service stopped when the test ends."""
    with ExitStack() as running:

        def start(config: str = "gateway", team: str = "Gateway") -> Pitcrew:
            use_team_config(Path(service_env["PITCREW_CONFIG_DIR"]), config, team)
            return Pitcrew(running.enter_context(TestClient(app)))

        yield start


@pytest.fixture
def pitcrew(start_pitcrew: StartPitcrew) -> Pitcrew:
    """The service started with Gateway with every feature, driven through the Run
    chain."""
    return start_pitcrew()


@pytest.fixture
def client(pitcrew: Pitcrew) -> TestClient:
    """The raw HTTP client of the started service: for the tests of HTTP itself."""
    return pitcrew.http


@pytest.fixture
def load_scenario(testops: FakeTestOps, gitlab: FakeGitLab) -> LoadScenario:
    """Loads a night of `data/scenarios/` into TestOps and GitLab, faked; gives its ids
    by role. One night per test."""

    def load(name: str) -> Night:
        if testops.night is not None:
            raise RuntimeError(f"A night is loaded already: {testops.night.name}")
        night = Night.load(name)
        testops.serve(night)
        gitlab.serve(night)
        return night

    return load
