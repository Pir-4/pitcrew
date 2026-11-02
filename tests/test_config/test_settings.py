from pathlib import Path

import pytest

from pitcrew.config.settings import Settings
from pitcrew.constants import ModelTier
from pitcrew.log import get_logger
from tests.support.logs import Logs


class ProbeSettings(Settings):
    """Settings with one field, to observe where `Settings` takes its values from."""

    probe: str = "default"


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PROBE", raising=False)
    for required in ("PITCREW_TRIGGER_TOKEN", "ALLURE_TOKEN", "GITLAB_TOKEN"):
        monkeypatch.setenv(required, "required-but-irrelevant-here")
    for required in ("ALLURE_ENDPOINT", "GITLAB_URL"):
        monkeypatch.setenv(required, "https://required-but-irrelevant.example")
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    (tmp_path / "src").mkdir()
    return tmp_path


def test_reads_service_env(workdir: Path) -> None:
    (workdir / "src/service.env").write_text("PROBE=from-service-env\n")

    assert ProbeSettings().probe == "from-service-env"


def test_environment_overrides_service_env(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (workdir / "src/service.env").write_text("PROBE=from-service-env\n")
    monkeypatch.setenv("PROBE", "from-environment")

    assert ProbeSettings().probe == "from-environment"


def test_groups_read_their_variables_by_name(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (workdir / "src/service.env").write_text(
        "ALLURE_ENDPOINT=https://from-service-env.example\nLITELLM_KEY=from-service-env\n"
    )
    monkeypatch.delenv("ALLURE_ENDPOINT")
    monkeypatch.delenv("LITELLM_KEY", raising=False)
    monkeypatch.setenv("PITCREW_WORK_DIR", "from-environment")
    monkeypatch.setenv("AGENT_MAX_TURNS", "5")
    monkeypatch.setenv("AGENT_MODEL_SENIOR", "claude-from-environment")

    settings = Settings()

    assert str(settings.allure.endpoint) == "https://from-service-env.example/"
    assert settings.litellm.key is not None
    assert settings.litellm.key.get_secret_value() == "from-service-env"
    assert settings.work_dir == Path("from-environment")
    assert settings.agent.max_turns == 5
    assert settings.agent.model(ModelTier.SENIOR) == "claude-from-environment"


def test_ignores_agent_env(workdir: Path) -> None:
    (workdir / ".env").write_text("PROBE=from-agent-env\n")

    assert ProbeSettings().probe == "default"


def test_masks_database_password_in_logs(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, logs: Logs
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "mysql+pymysql://pitcrew:db-password@host/pitcrew"
    )

    settings = Settings()
    get_logger(__name__).info("Database", database_url=str(settings.database_url))

    assert "db-password" not in logs.text
    assert "host/pitcrew" in logs.text
