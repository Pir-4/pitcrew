from pathlib import Path

from pitcrew.config.team import AllureConfig, GitLabConfig, TeamConfigs


def test_team_config_takes_missing_values_from_base(tmp_path: Path) -> None:
    (tmp_path / "base.yaml").write_text(
        "allure:\n  project_id: 3\ngitlab:\n  project_path: gateway/qa_automation\n"
    )
    (tmp_path / "gateway.yaml").write_text(
        "name: Gateway\n"
        "allure:\n  nightly_test_plan_id: 1387\n  rerun_test_plan_id: 12396\n"
    )

    config = TeamConfigs(tmp_path).get("Gateway")

    assert config.allure == AllureConfig(
        project_id=3, nightly_test_plan_id=1387, rerun_test_plan_id=12396
    )
    assert config.gitlab == GitLabConfig(project_path="gateway/qa_automation")
