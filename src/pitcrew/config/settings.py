from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import AnyUrl, Field, HttpUrl, SecretStr, UrlConstraints, create_model
from pydantic_settings import BaseSettings, SettingsConfigDict

from pitcrew.constants import ModelTier
from pitcrew.log import LogFormat, mask_secrets

type SqliteUrl = Annotated[AnyUrl, UrlConstraints(allowed_schemes=["sqlite"])]
type MySqlUrl = Annotated[
    AnyUrl, UrlConstraints(allowed_schemes=["mysql+pymysql"], host_required=True)
]
type DatabaseUrl = SqliteUrl | MySqlUrl

_ENV_SOURCES = SettingsConfigDict(
    env_file="src/service.env", extra="ignore", hide_input_in_errors=True
)


class _EnvSettings(BaseSettings):
    """Settings read from `_ENV_SOURCES`; every secret field is masked in the logs from the
    moment it is read."""

    model_config = _ENV_SOURCES

    def model_post_init(self, context: Any) -> None:
        mask_secrets(
            value.get_secret_value()
            for value in self.__dict__.values()
            if isinstance(value, SecretStr)
        )


class AllureSettings(_EnvSettings):
    """Allure TestOps: `ALLURE_*`."""

    model_config = SettingsConfigDict(**_ENV_SOURCES, env_prefix="ALLURE_")

    endpoint: HttpUrl
    token: SecretStr = Field(min_length=1)


class GitLabSettings(_EnvSettings):
    """GitLab, where the test repo and its pipelines live: `GITLAB_*`."""

    model_config = SettingsConfigDict(**_ENV_SOURCES, env_prefix="GITLAB_")

    url: HttpUrl
    token: SecretStr = Field(min_length=1)


class LiteLlmSettings(_EnvSettings):
    """The internal LiteLLM the Agent reaches models through, with a bearer key: `LITELLM_*`.
    The key is optional so that the service starts without it; an Agent task fails without
    it."""

    model_config = SettingsConfigDict(**_ENV_SOURCES, env_prefix="LITELLM_")

    url: HttpUrl = HttpUrl("https://litellm.ston.fi")
    key: SecretStr | None = None


class AgentSettings(_EnvSettings):
    """The Agent, `AGENT_*`: its models and the limits of every Agent task.

    Attributes:
        model_junior: The model of `ModelTier.JUNIOR` as LiteLLM names it; `model_middle` and
            `model_senior` likewise. A new version announced by the LiteLLM admins is one variable.
        max_turns: Turns an Agent task may take.
        max_budget_usd: Cost of an Agent task, as the SDK estimates it on the client side.
        timeout_seconds: Wall-clock time of an Agent task, after which Pitcrew stops the
            Agent's process.
    """

    model_config = SettingsConfigDict(**_ENV_SOURCES, env_prefix="AGENT_")

    model_junior: str = "claude-haiku-5-5"
    model_middle: str = "claude-sonnet-5-5"
    model_senior: str = "claude-opus-5-5"
    max_turns: int = Field(default=30, gt=0)
    max_budget_usd: float = Field(default=1.0, gt=0)
    timeout_seconds: float = Field(default=600, gt=0)

    def model(self, tier: ModelTier) -> str:
        """The model of a tier, as LiteLLM names it.

        Args:
            tier: How strong a model the Agent task needs.
        """
        return getattr(self, f"model_{tier}")


class Settings(_EnvSettings):
    """Service config: the service's own values, then a group per external service and one
    for the Agent, each reading its variables by their prefix.

    The root `.env` belongs to the development agent and is never read here. At deploy, Helm
    injects the same variables into the environment.

    Attributes:
        work_dir: Where Pitcrew keeps the clone of the test repo, the Working copies and the
            Agent's Claude state; a volume at deploy.
    """

    trigger_token: SecretStr = Field(
        min_length=1, validation_alias="PITCREW_TRIGGER_TOKEN"
    )
    database_url: DatabaseUrl
    config_dir: Path = Field(
        default=Path("config"), validation_alias="PITCREW_CONFIG_DIR"
    )
    work_dir: Path = Field(
        default=Path("var/workspace"), validation_alias="PITCREW_WORK_DIR"
    )
    allure: AllureSettings = Field(default_factory=AllureSettings)
    gitlab: GitLabSettings = Field(default_factory=GitLabSettings)
    litellm: LiteLlmSettings = Field(default_factory=LiteLlmSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)

    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)
        # The DB password is part of a URL, not a secret field: masked on its own.
        if self.database_url.password:
            mask_secrets([self.database_url.password])

    def secret(self, name: str) -> SecretStr | None:
        """A secret a Team config names by its variable, read the way the fields are: the
        environment, then the env file. Masked in the logs, as the fields are.

        Args:
            name: The variable, e.g. `SLACK_WEBHOOK_GATEWAY`.

        Returns:
            The secret, or `None` when the variable is unset or empty.
        """
        source = create_model(
            "TeamSecret",
            __base__=_TeamSecret,
            value=(SecretStr | None, Field(default=None, validation_alias=name)),
        )
        value = source().value  # ty: ignore[unresolved-attribute]
        if value:
            mask_secrets([value.get_secret_value()])
        return value if value and value.get_secret_value() else None


class _TeamSecret(BaseSettings):
    """Reads one variable named at runtime with the sources and files of `Settings`."""

    model_config = _ENV_SOURCES


class LogSettings(BaseSettings):
    """How the service logs. Read apart from `Settings`: logging is set up when the app is
    imported, before the startup validates the rest of the config, so that its errors are
    logged too."""

    model_config = _ENV_SOURCES

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: LogFormat = LogFormat.JSON


@lru_cache
def get_settings() -> Settings:
    return Settings()
