from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pitcrew.config.settings import get_settings
from pitcrew.main import app
from tests.support.config import use_config
from tests.support.constants import REPO_CONFIG, SLACK_WEBHOOK_VARIABLE

# Gateway with the Conclusion and no `slack` section to say where it goes.
CONCLUSION_WITHOUT_SLACK = (
    "name: Gateway\nallure:\n  project_id: 3\n  nightly_test_plan_id: 1387\n"
    "  rerun_test_plan_id: 12396\nfeatures:\n  conclusion: true\n"
)
# Gateway's file naming another Team: the file is how a trigger's Team is found.
GATEWAY_FILE_OF_WALLET = (
    "name: Wallet\nallure:\n  project_id: 3\n  nightly_test_plan_id: 1387\n"
    "  rerun_test_plan_id: 12396\n"
)


@pytest.mark.parametrize(
    ("env", "team_config", "error", "match"),
    [
        # `nightly_test_plan` for `nightly_test_plan_id`, and no Rerun test plan.
        pytest.param(
            {},
            (
                "{}\n",
                "name: Gateway\nallure:\n  project_id: 3\n  nightly_test_plan: 1387\n",
            ),
            ValidationError,
            r"allure\.nightly_test_plan\s+Extra inputs are not permitted",
            id="an invalid Team config",
        ),
        pytest.param(
            {},
            ((REPO_CONFIG / "base.yaml").read_text(), GATEWAY_FILE_OF_WALLET),
            ValueError,
            r"Team config gateway\.yaml names team 'Wallet': its file must be wallet\.yaml",
            id="a Team config in a file not named after its Team",
        ),
        # Empty in the environment, so that a value in a local service env file does not
        # count.
        pytest.param(
            {SLACK_WEBHOOK_VARIABLE: ""},
            None,
            ValueError,
            SLACK_WEBHOOK_VARIABLE,
            id="a Conclusion without its Slack webhook",
        ),
        pytest.param(
            {},
            ((REPO_CONFIG / "base.yaml").read_text(), CONCLUSION_WITHOUT_SLACK),
            ValidationError,
            r"features\.conclusion needs slack\.webhook_variable",
            id="a Conclusion without a Slack webhook variable",
        ),
        pytest.param(
            {"PITCREW_TRIGGER_TOKEN": ""},
            None,
            ValidationError,
            "PITCREW_TRIGGER_TOKEN",
            id="an empty trigger token",
        ),
        pytest.param(
            {"ALLURE_ENDPOINT": "testops.ston.fi"},
            None,
            ValidationError,
            r"AllureSettings\s+endpoint",
            id="an Allure endpoint without a scheme",
        ),
        pytest.param(
            {"DATABASE_URL": "mysql+pymysql:/user:db-password@host/pitcrew"},
            None,
            ValidationError,
            r"Settings\s+database_url",
            id="an unparsable database URL",
        ),
    ],
)
def test_startup_is_stopped(
    service_env: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
    team_config: tuple[str, str] | None,
    error: type[Exception],
    match: str,
) -> None:
    """`team_config` is the base and the Gateway config, YAML, in place of the test's
    own; `match` is what the error names."""
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    if team_config is not None:
        base, gateway = team_config
        use_config(tmp_path, monkeypatch, base=base, gateway=gateway)
    get_settings.cache_clear()

    with pytest.raises(error, match=match), TestClient(app):
        pass


def test_unparsable_database_url_is_not_shown(
    service_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A settings value can be a secret: the error names the field, not the value."""
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql:/user:db-password@host/pitcrew")
    get_settings.cache_clear()

    with pytest.raises(ValidationError) as error, TestClient(app):
        pass

    assert "db-password" not in str(error.value)
