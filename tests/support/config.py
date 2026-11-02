from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from pitcrew.config.settings import get_settings
from pitcrew.config.team import TeamConfig, TeamConfigs, team_config_file
from tests.support.constants import REPO_CONFIG, TEAM_CONFIGS


def use_team_config(config_dir: Path, variant: str, team: str = "Gateway") -> None:
    """Fills a Team config directory as the service reads it: the repo's real `base.yaml` and
    the named variant of `data/team_configs/` as the config of the Team, Gateway by
    default. A variant names no Team: the Team's `name` is written over it, in the file the
    service looks the Team up by."""
    config_dir.mkdir(exist_ok=True)
    (config_dir / "base.yaml").write_text((REPO_CONFIG / "base.yaml").read_text())
    (config_dir / team_config_file(team)).write_text(
        f"name: {team}\n" + (TEAM_CONFIGS / f"{variant}.yaml").read_text()
    )


def load_team_config(variant: str, team: str = "Gateway") -> TeamConfig:
    """The named variant of `data/team_configs/` as the config of the Team, Gateway by
    default, loaded as the service loads it: for a test of a Step's part that takes a
    `TeamConfig`."""
    with TemporaryDirectory() as config_dir:
        use_team_config(Path(config_dir), variant, team)
        return TeamConfigs(Path(config_dir)).get(team)


def use_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, base: str, gateway: str
) -> None:
    """Points the service at a Team config directory with these two files, `gateway` as
    Gateway's config file: for the tests of Team config validation only, whose YAML is the
    input under test."""
    config_dir = tmp_path / "inline_config"
    config_dir.mkdir()
    (config_dir / "base.yaml").write_text(base)
    (config_dir / team_config_file("Gateway")).write_text(gateway)
    monkeypatch.setenv("PITCREW_CONFIG_DIR", str(config_dir))
    get_settings.cache_clear()
