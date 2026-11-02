# Run chain tests

The wiring of the Run chain, through HTTP: a Step is triggered for a recorded night, and the test
checks what came of it. The rules themselves are tested in `tests/test_steps/`; here a test checks
that a Step applies a rule and acts on its answer, not every case of it.

## The scenario and the driver

A test loads its night once, then drives the service through the `pitcrew` fixture
(`tests/support/run_chain.py`):

```python
def test_night_run_with_failures_starts_a_rerun(
    pitcrew: Pitcrew, load_scenario: LoadScenario, gitlab: FakeGitLab
) -> None:
    night = load_scenario("night_with_failures")

    answer = pitcrew.trigger_night_run(night)

    assert pitcrew.run_chain(answer.trace_id)["runs"][1]["expected_test_count"] == 223
    assert len(gitlab.created_pipelines) == 1
```

- `pitcrew.trigger_night_run(night, **overrides)` and `pitcrew.trigger_night_rerun(night,
  **overrides)` send the trigger of the night's Nightly run or Rerun; `overrides` replace fields
  of the trigger (`team="Nobody"`, `allure_launch_id=night.rerun.launch_id`), and `token`
  replaces the bearer token (`token=None` sends none). Each gives an `Answer`:
  `status_code`, `trace_id`, `detail` (why it was rejected, as the API gives it), `reason`
  (the detail as one line: `environment: Input should be ...` for a field that failed validation),
  `request_id`, `body`.
- `pitcrew.run_chain(trace_id)` is the Run chain as `GET /run-chains/{trace_id}` shows it:
  its Runs are `runs`, a list in the order they were started (`[0]` the Nightly run, `[1]` the
  Rerun once started); whether a Step has finished shows in `status` (`activity: done`, or the
  chain moved on to the next Step); a Step that failed shows `activity: failed` and the
  chain's `failure_reason`.
- `start_pitcrew(config="gateway_without_rerun")` gives the driver of the service started
  with another Team config variant (see `tests/data/AGENTS.md`); `pitcrew` is
  `start_pitcrew()`. `start_pitcrew(team="Farming")` writes the variant as the config of
  another Team (`farming.yaml`), for a test of a Team that exists only as a Team config.

The driver sends the bearer token, builds the trigger bodies and takes the trace id out of the
answer: a test never does. Every trigger goes through the driver, a rejected one too (the
rejected triggers are one table in `test_triggers.py`: a row, a `Rejection`, per case, the
trigger sent with its overrides, the status code and reason, and, where the case needs them,
another scenario, an error switch of TestOps, or the Step left without a class in `STEPS`, dropped
with `monkeypatch` for the `501`). Only a test of HTTP itself that sends no
trigger (a malformed trace id, `GET /run-chains` without a token) takes the raw `client`.

## Assert on outcomes, not on requests

A test checks what the Run chain left behind, never how it got there:

- what `pitcrew.run_chain(...)` shows, and what the trigger was answered;
- what the fakes hold: `testops.written_test_plans` (the Rerun test plan written),
  `gitlab.created_pipelines` (branch, inputs, variables), `slack.posted` (compared as
  `post_text` with a constant of `tests/data/conclusions.py`);
- what was logged, through the `logs` fixture.

No test asserts on the order, the paths or the bodies of the requests a fake got. What a fake
counts of its reads (`testops.searched_launches`, `testops.read_test_results`,
`testops.checked_launches`) is asserted only where the count is the behaviour: a broken
pipeline's results not searched, each Failed test's error read once, a resumed or repeated Step
reading nothing again, a rejected trigger checking no launch.

## A test

Given / when / then, three blocks separated by blank lines: the given block loads the night,
picks the config and sets a fake's error switch, and sends the triggers the test does not
check; the when block is the one trigger under test; the then block asserts. A behaviour that
spans the Run chain (what `test_logging.py` checks across its Steps) has no one trigger: there
the when block sends the triggers of the chain under test. A docstring
only for a reason the code cannot show; what a night is goes into its scenario's README, not
into a comment of the test.
