# Test support

Code the tests share. Not a test module: pytest collects nothing here.

| Module | What it holds |
|--------|---------------|
| `constants.py` | The values of the service env the tests start with: the trigger token `TOKEN` and its header `AUTH`; TestOps (`ALLURE_ENDPOINT`, `ALLURE_TOKEN`, `ALLURE_PROJECT`, Gateway's project), GitLab (`GITLAB_URL`, `GITLAB_TOKEN`, `QA_AUTOMATION`, the test repo's path as the API takes it) and Slack (`SLACK_WEBHOOK_VARIABLE` and its value `SLACK_WEBHOOK`), the Agent (`LITELLM_URL`, `LITELLM_KEY`, the models of the tiers, `MAX_TURNS`, `MAX_BUDGET_USD`, `TIMEOUT_SECONDS`). The paths of the test data: `TESTS`, `REPO_CONFIG` (the repo's real `config/`), `TEAM_CONFIGS`, `SCENARIOS`. `UNKNOWN_TRACE_ID`, a trace id no Run chain has |
| `fakes.py` | `FakeTestOps`, `FakeGitLab`, `FakeSlack`: the external services behind `httpx` transports; TestOps and GitLab answer from the night they serve. Each keeps the state a test asserts on, never the requests: the test plans written to TestOps and what was read of its launches, the pipelines GitLab created (`CreatedPipeline`: branch, inputs, variables), the posts Slack took |
| `scenarios.py` | `Night`, a scenario of `tests/data/scenarios/` with its runs (`Run`: ids and recorded answers) by role, and what it recorded about a run by one of its ids (`recorded_of`) or about a Failed test (`recorded_test_result`), which the fakes answer with; `LoadScenario`, the type of the `load_scenario` fixture |
| `logs.py` | `Logs`, what the `logs` fixture gives: the JSON log output, parsed |
| `run_chain.py` | `Pitcrew`, the Run chain driver the `pitcrew` fixture gives (see `tests/test_run_chain/AGENTS.md`), with `Answer`, what a trigger was answered (`reason`: why it was rejected, as one line), and `StartPitcrew`, the type of the `start_pitcrew` fixture; `night_run_body` / `night_rerun_body`, the trigger bodies the driver sends |
| `config.py` | `use_team_config` (a Team config directory of the test's own: the repo's base config and a named variant as the config of a Team, Gateway by default, with the Team's `name` written over it, in the file `team_config_file` names), `load_team_config` (a variant loaded as the service loads it, for a test of a Step's part that takes a `TeamConfig`), `use_config` (inline YAML as Gateway's file, for the tests of Team config validation only) |
| `agent.py` | `FakeRunner`, the Claude Agent SDK faked: streams the messages it is given (by default the answer `ANSWER`), fails or hangs, keeps each call (`AgentCall`: prompt, options, the files of the Working copy); `result_message`, `assistant_message`, the SDK's messages |
| `git.py` | `Origin`, `qa_automation` on GitLab as a local bare repo (`commit` to a branch); `CLONE_URL`, `SKILL`, `REPO_SETTINGS`, what it holds; `git`, `clone_in` and `worktrees`, what Pitcrew's clone in a work dir holds |
| `slack_post.py` | `post_text`: a posted Block Kit message as the lines a person reads in Slack, the test-cases search decoded into its AQL; it decodes the actual, never builds an expected post |

Imports go one way:

- any test module and any `conftest.py` may import `tests.support`;
- `tests.support` never imports a test module or a `conftest.py`;
- test modules never import each other: what two of them share moves here;
- production code never imports from `tests`.

A fixture is not defined here: it goes into a `conftest.py` (see `tests/AGENTS.md`). Names
follow the tests' rules: no leading underscore, nothing named `test*`.
