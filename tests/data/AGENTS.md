# Test data

What the tests run on and compare with: the nights of the Run chain as GitLab and TestOps
answered them, the Team configs they run under, and the expected values, written as a person reads them. Not a test module:
pytest collects nothing here.

| Path | What it holds |
|------|---------------|
| `scenarios/` | One folder per night of the Run chain, recorded from the real GitLab and TestOps (see Scenarios) |
| `team_configs/` | The Team config variants of Gateway (see Team configs) |
| `conclusions.py` | The expected Conclusions: one constant per case, named after it (`BROKEN_RERUN`, `RERUN_WITH_11_ERROR_GROUPS`) |

## Scenarios

A scenario is one night: a Nightly run and, when the night gets that far, its Rerun. A Run chain
test loads it by name with the `load_scenario` fixture, once, and takes the ids from what it
gives (`night.nightly.launch_id`, `night.rerun.pipeline_id`): a test holds no id of its own.
Nights with the same behaviour come as `pytest.param` rows of one test.

| Scenario | The night |
|----------|-----------|
| `night_with_failures` | 685 Failed tests: the Rerun test plan written, the Rerun created |
| `night_with_failures_rerun_broken` | The same night, its Rerun broken: 2 results of ~223 expected |
| `green_night` | No Failed test: the chain ends |
| `night_with_one_result` | Broken: one result of 1675 expected |
| `canceled_night` | Broken: the pipeline canceled at `test`, no result read |
| `launch_without_pipeline` | A launch uploaded from an IDE: the trigger is rejected |
| `small_night_failing_on_rerun` | Two Failed tests failing again: one Error group and the rest |
| `small_night_green_on_rerun` | The same two tests, green on the Rerun |
| `small_night_rerun_with_error_groups` | A Rerun of 5 Failed tests: two Error groups and the rest |

A scenario folder holds:

- `README.md`: what the night is, where and when each run was recorded, and which recording
  plays another role (a run of a branch standing for a Nightly run, another night's Rerun
  standing for this one's);
- `scenario.json`: the ids by role, `nightly` and `rerun`, each with its `pipeline_id`,
  `launch_id` and `test_plan_id` (the test plan its Team config names for that role);
- `nightly/` and `rerun/`: the recorded answers about that run, named by role.

| File | Request |
|------|---------|
| `pipeline_jobs.json` | `GET /api/v4/projects/gateway%2Fqa_automation/pipelines/<pipeline>/jobs?per_page=100`: Pitcrew reads `name`, `stage`, `status`, `allow_failure` |
| `pipeline.json` (Rerun) | What `POST /api/v4/projects/gateway%2Fqa_automation/pipeline` answers: Pitcrew reads its `id`. Recorded as `GET .../pipelines/<pipeline>`, the same body: creating a pipeline starts real tests on an Environment |
| `launch_job_runs.json` | `GET /api/rs/launch/<launch>/job`: `externalId` is the GitLab pipeline id |
| `failed_tests_page<n>.json` | `GET /api/rs/testresult/__search?projectId=3&rql=launch = <launch> and status in ["failed", "broken"]&page=<n>&size=500&sort=id,ASC` |
| `result_count.json` | `GET /api/rs/testresult/__search?projectId=3&rql=launch = <launch>&page=0&size=1&sort=id,ASC`: Pitcrew reads only `totalElements` |
| `test_plan.json` | Nightly: `GET /api/rs/testplan/<plan>`, Pitcrew reads `testCasesCount`. Rerun: what `PATCH /api/rs/testplan/<plan>` answers (Pitcrew reads nothing of it) |
| `test_plan_request.json` (Rerun) | The body Pitcrew sends with that `PATCH`, recorded with it: what a test expects the Nightly run to write |
| `test_results.json` | `GET /api/rs/testresult/<result>` for every Failed test of the launch, as `{"<result>": body}`; each body cut down to `id`, `launchId`, `testCaseId`, `name`, `status` and `message` (the rest is mostly stack traces) |

A file is only there when a test reads it. Copying a recording between scenarios is allowed;
the README says where it comes from.

`FakeTestOps` and `FakeGitLab` (`tests/support/fakes.py`) answer from the loaded night, by the
ids in the request, and the way the real services do for what the night does not hold:

- TestOps: a launch, a search or a test plan the night does not hold: `403 Forbidden`, as
  TestOps answers a launch that does not exist; a test result not in `test_results.json`:
  `404`; another token: `401 auth.bad-token`; another `projectId` or `rql`: `400 invalid query`;
- GitLab: the jobs of a pipeline the night does not hold: `404 Not found`; another token:
  `401 Unauthorized`; any other request: `404 Project Not Found`.

A switch of a fake may make an answer an error (`not_found_launches`, `token_revoked`,
`pipeline_jobs_error`, `create_pipeline_error`, Slack `failures`), never change the data a test runs on: other data is another scenario.

## Recording a scenario

A new night gets real answers, recorded, never written by hand.

1. Find the runs that show the case. Note the launch in TestOps and, from
   `GET /api/rs/launch/<launch>/job`, its pipeline. A run of a branch may play the Nightly run,
   and a recorded Rerun of another night may play this night's Rerun: say so in the README.
2. Create `scenarios/<night>/` with `scenario.json` and a `README.md`, and record each file the
   night's Steps read into `nightly/` or `rerun/`, named as in the table above. Request exactly
   what the clients send.
   - GitLab: `glab api` authenticates with the agent's own token and prints the body:

     ```bash
     glab api "projects/gateway%2Fqa_automation/pipelines/<pipeline>/jobs?per_page=100" \
       > tests/data/scenarios/<night>/<role>/pipeline_jobs.json
     ```

   - TestOps: authenticate through the service settings, so the token stays out of the
     transcript; this prints the status only (`Settings` also requires
     `PITCREW_TRIGGER_TOKEN`; any value in the environment will do):

     ```python
     # uv run python record.py '<path?query>' tests/data/scenarios/<night>/<role>/<file>.json
     import json
     import sys
     from pathlib import Path

     import httpx2 as httpx

     from pitcrew.config.settings import AllureSettings

     allure = AllureSettings()
     response = httpx.get(
         f"{str(allure.endpoint).rstrip('/')}/api/rs{sys.argv[1]}",
         headers={"Authorization": f"Api-Token {allure.token.get_secret_value()}"},
     )
     print(response.status_code)
     Path(sys.argv[2]).write_text(json.dumps(response.json(), indent=2) + "\n")
     ```

     For `test_results.json`, request `/testresult/<id>` for every result of the launch's
     `failed_tests_page0.json` the same way and write them into one file, each body cut down.
3. A write (creating a pipeline, writing a test plan) changes the real object: record it only on
   an object Pitcrew owns (the Rerun test plan) or from a Rerun you were going to run anyway
   (see the Rerun check in `docs/roadmap.md`), and keep the body sent next to the answer.
4. Add the scenario to the table above. Done when its test is green against the recorded
   answers.

## Team configs

The service reads the repo's real `config/base.yaml` with a Gateway config from
`team_configs/` over it: `use_team_config` copies both into a directory of the test's own, the
variant as the Team's file (`gateway.yaml`) with the Team's `name` written over it; a
variant names no Team. The tests never hold a copy of the base config, so a change to it shows
in them. A Run chain test names its variant through `start_pitcrew(config=...)`; the
`pitcrew` fixture runs `gateway`.

| Variant | Gateway |
|---------|------------|
| `gateway` | With every feature: Rerun, Conclusion, Error groups |
| `gateway_without_rerun` | Without the Rerun: a Nightly run with failures ends the chain |
| `gateway_without_conclusion` | Without the Conclusion: nothing is posted, and the Run chain records no Conclusion |
| `gateway_without_error_groups` | Without the Error groups: the Conclusion counts the Failed tests of the Rerun |
| `gateway_rerun_on_a_debug_branch` | Rerunning on `pitcrew-debug` with inputs of its own (one of them Pitcrew's own `TEST_PLAN_ID`) |
| `gateway_with_a_low_max_failed_ratio` | Taking over 10% of Failed tests for a down Environment: `night_with_failures` (11%) is broken |

A variant is a whole Team file, written like `config/gateway.yaml`: what it changes is the
point of its name and its first comment. A new case that needs another setting gets a new
variant, named after what it changes, and a row here; a test never edits a variant's YAML. The
thresholds stay those of the base config: a night that passes only under a tuned threshold
needs the test plan it ran recorded (as `green_night` and `small_night_*` have), not a variant.

## Expected posts

- A post is the text Slack shows, as `tests.support.slack_post.post_text` gives it: the
  header, `---` for a divider, then a line per section (a run block is two lines); links stay
  `<url|label>`.
- A TestOps test-cases link shows its search decoded, as AQL: `test-cases?search=id in [124669]`.
  Its encoding is checked once, in `tests/test_clients/test_links.py`.
- The URLs are the test ones of the service env (`https://gitlab.example`,
  `https://testops.example`); the Team is Gateway on staging.
- A constant is written by hand (or taken from a run and read line by line before it is
  committed), never built by code: a constant built the way production builds the post would
  agree with it by construction.
- A comment above a constant says what the case is when its name cannot.
- One constant serves both levels: the test of `conclusion_message` in `tests/test_steps/` and the
  end-to-end test in `tests/test_run_chain/` that posts the same Conclusion compare with it.
