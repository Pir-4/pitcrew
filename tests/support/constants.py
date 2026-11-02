from pathlib import Path

TOKEN = "test-trigger-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
TESTS = Path(__file__).parent.parent
# The Team configs the service is deployed with: the tests read its `base.yaml`.
REPO_CONFIG = TESTS.parent / "config"
# The Team config variants of Gateway the tests run with (see data/AGENTS.md).
TEAM_CONFIGS = TESTS / "data" / "team_configs"
# The nights of the Run chain, recorded from the real GitLab and TestOps (see
# data/AGENTS.md).
SCENARIOS = TESTS / "data" / "scenarios"
ALLURE_ENDPOINT = "https://testops.example"
ALLURE_TOKEN = "test-allure-token"
# `allure.project_id` of Gateway in data/team_configs/.
ALLURE_PROJECT = 3
GITLAB_URL = "https://gitlab.example"
GITLAB_TOKEN = "test-gitlab-token"
# `gitlab.project_path` in the repo's config/base.yaml, as the GitLab API takes it in a path.
QA_AUTOMATION = "gateway%2Fqa_automation"
# `slack.webhook_variable` of Gateway in data/team_configs/, and its value.
SLACK_WEBHOOK_VARIABLE = "SLACK_WEBHOOK_GATEWAY"
SLACK_WEBHOOK = "https://hooks.slack.example/services/T000/B000/test-webhook-secret"
LITELLM_URL = "https://litellm.example"
LITELLM_KEY = "test-litellm-key"
# The models of the tiers; the smoke asks the junior one.
JUNIOR_MODEL = "claude-test-junior"
MIDDLE_MODEL = "claude-test-middle"
SENIOR_MODEL = "claude-test-senior"
# The limits of every Agent task; the timeout short enough for a test to outlive it.
MAX_TURNS = 7
MAX_BUDGET_USD = 0.5
TIMEOUT_SECONDS = 0.2

# A trace id no Run chain has.
UNKNOWN_TRACE_ID = "00000000-0000-4000-8000-000000000000"
