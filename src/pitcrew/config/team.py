from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from pitcrew.clients.gitlab import InputValue

BASE_CONFIG = "base.yaml"

type Ratio = Annotated[float, Field(ge=0, le=1)]


def team_config_file(team: str) -> str:
    """The name of a Team's config file in `PITCREW_CONFIG_DIR`: the Team lowercased.

    Args:
        team: The Team, in any spelling, e.g. `Gateway` or `gateway`.
    """
    return f"{team.lower()}.yaml"


class UnknownTeamException(Exception):
    """A Team without a Team config: Pitcrew is not set up for it.

    `str()` is the reason, fit to show the caller: `No Team config for team 'Wallet'`.

    Attributes:
        team: The Team as it was asked for.
    """

    def __init__(self, team: str) -> None:
        """
        Args:
            team: The Team as it was asked for.
        """
        super().__init__(f"No Team config for team '{team}'")
        self.team = team


class AllureConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: int
    nightly_test_plan_id: int
    rerun_test_plan_id: int


class GitLabConfig(BaseModel):
    """The test repo on GitLab.

    Attributes:
        project_path: The project of the test repo, e.g. `gateway/qa_automation`.
        test_job: The job of its pipeline that runs the tests: a Nightly run whose pipeline
            failed or was canceled before this job finished is broken.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_path: str
    test_job: str = "test"


class RerunConfig(BaseModel):
    """How the Failed tests of a Nightly run are rerun.

    Attributes:
        branch: Branch of the test repo the Rerun pipeline runs on; another one to debug the
            chain.
        pipeline_inputs: `spec:inputs` of the test repo's pipeline set on every Rerun, over
            their defaults, e.g. `RUN_WITH_FLAGS: true`, `NOTIFY_SLACK: true`. The inputs
            Pitcrew sets itself (`PROJECT_NAME`, `ENVIRONMENT`, `TEST_PLAN_ID`) win over these.
        max_failed_ratio: A Nightly run with a larger share of Failed tests is broken, not
            rerun: the Environment is likely down, and a Rerun would block it for hours.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    branch: str = "master"
    pipeline_inputs: dict[str, InputValue] = {}
    max_failed_ratio: Ratio = 0.5


class SlackConfig(BaseModel):
    """The Team's Slack channel.

    Attributes:
        webhook_variable: The variable holding the incoming webhook of the channel, e.g.
            `SLACK_WEBHOOK_GATEWAY`: the URL is a secret, so it lives in the environment.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    webhook_variable: str


class FeaturesConfig(BaseModel):
    """What Pitcrew does for the Team.

    Attributes:
        rerun: Rerun the Failed tests of a Nightly run with failures.
        conclusion: Post the Conclusion about a Run chain to the Team's Slack channel.
        error_groups: Recognize the Error groups among the Failed tests of the Rerun, store
            them with the Run chain and list them in the Conclusion.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    rerun: bool = False
    conclusion: bool = False
    error_groups: bool = False


class TeamConfig(BaseSettings):
    """The non-secret settings of one Team: `base.yaml` with `<team lowercased>.yaml` over it.

    A misspelled key fails the startup instead of being silently ignored.

    Attributes:
        name: The Team as `qa_automation` spells its `PROJECT_NAME`, e.g. `Gateway`: the
            Run chain stores it and the Rerun and the Conclusion use it, whatever spelling
            the trigger came with. Its file is named after it (`team_config_file`).
        broken_below_ratio: A Nightly run with fewer results than this share of its nightly
            test plan's test cases is broken: the tests did not actually run.
    """

    model_config = SettingsConfigDict(extra="forbid", frozen=True)

    name: str
    allure: AllureConfig
    gitlab: GitLabConfig
    broken_below_ratio: Ratio = 0.5
    rerun: RerunConfig = RerunConfig()
    slack: SlackConfig | None = None
    features: FeaturesConfig = FeaturesConfig()

    @model_validator(mode="after")
    def _conclusion_has_a_channel(self) -> Self:
        if self.features.conclusion and self.slack is None:
            raise ValueError("features.conclusion needs slack.webhook_variable")
        return self

    @classmethod
    def load(cls, config_dir: Path, team_file: Path) -> Self:
        """Reads `base.yaml`, then the Team's file over it, deep-merged by pydantic-settings.

        Args:
            config_dir: The directory that holds `base.yaml`.
            team_file: The Team's YAML file.

        Raises:
            ValidationError: The merged config is invalid.
            ValueError: The file is not named after the Team its `name` says.
        """
        yaml = YamlConfigSettingsSource(
            cls, yaml_file=[config_dir / BASE_CONFIG, team_file], deep_merge=True
        )
        config = cls(**yaml())
        if team_file.name != team_config_file(config.name):
            raise ValueError(
                f"Team config {team_file.name} names team '{config.name}': "
                f"its file must be {team_config_file(config.name)}"
            )
        return config

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Only what `load` passes in: a Team config never comes from the environment.
        return (init_settings,)


class TeamConfigs:
    """Every Team config of `PITCREW_CONFIG_DIR`, validated when loaded."""

    def __init__(self, config_dir: Path) -> None:
        """Loads and validates every Team config of the directory.

        Args:
            config_dir: The directory of `base.yaml` and one `<team>.yaml` per Team.

        Raises:
            FileNotFoundError: The directory has no `base.yaml`.
            ValidationError: A Team config is invalid.
            ValueError: A Team config's file is not named after its Team.
        """
        if not (config_dir / BASE_CONFIG).is_file():
            raise FileNotFoundError(f"No {BASE_CONFIG} in {config_dir.resolve()}")
        self._teams = {
            path.name: TeamConfig.load(config_dir, path)
            for path in sorted(config_dir.glob("*.yaml"))
            if path.name != BASE_CONFIG
        }

    def __iter__(self) -> Iterator[TeamConfig]:
        return iter(self._teams.values())

    def get(self, team: str) -> TeamConfig:
        """The config of a Team, found whatever the spelling of its name.

        Args:
            team: The Team in any spelling, e.g. `Gateway` or `gateway`; the config's
                `name` is the spelling to use from here on.

        Raises:
            UnknownTeamException: The Team has no config.
        """
        config = self._teams.get(team_config_file(team))
        if config is None:
            raise UnknownTeamException(team)
        return config
