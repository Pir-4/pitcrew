# Pitcrew — MVP plan (Stage 1)

Living document: the Stage 1 breakdown from the [roadmap](roadmap.md) into the Jira tasks under
epic GW-1, one task per epic, worked one at a time. Jira is the source of truth for the
tasks; this file holds the shape of the plan, what each task must produce, and the questions to
settle when its grilling starts. Per-task details live in the GitLab spec issues `/to-spec`
produces.

## Scope

- **Local first.** Until the demo the service runs from a laptop with personal tokens, triggered
  by hand or by a local poller during the author's on-call; nothing in this plan waits for the
  deploy. Deploy, CI integration and security approval are the Rollout phase in the
  [roadmap](roadmap.md#rollout--after-the-mvp-demo).
- **One team: Gateway.** A team is a config file (`config/<team>.yaml` layered over
  `config/base.yaml`: Allure project id, nightly and rerun test plan ids, rerun branch and
  pipeline inputs, thresholds, Slack webhook variable, feature flags); the pipeline reads the
  config, no team constants in code. The environment is not config: it comes with each trigger.
  Adding another team after the MVP is approved means adding a file.
- **What the MVP fixes: test drift only** — models and schemas first (GW-4, GW-6),
  then test-ids (GW-7). Flake comes for free from the rerun. The environment / likely bug /
  unsure classes and the full morning summary by class are not in this round; they come once
  the drift flow works.
- **Sources of truth:** Allure TestOps is the source of test results (which tests failed, error
  text, history, attachments). GitLab is used to check that the nightly run actually happened and
  is usable, to trigger reruns and verification runs, to read the test repo and to open MRs.
- **The engine is Claude Code** running inside the service (GW-5), pointed at LiteLLM. It
  reads the test repo and uses the agent tooling `qa_automation` already has (AGENTS.md, skills,
  domain docs). Pitcrew orchestrates: decides *what* to hand to the agent and *what* it may do;
  the agent does the code work.
- **Pitcrew never runs tests itself.** A fix is verified by a pipeline of `qa_automation` on the
  fix branch; the service needs no environment credentials. UI checks for test-ids (GW-7)
  go through Playwright CLI / MCP from the agent, which is the one place that needs network
  access to the stage UI.
- **Jira is deferred** (see roadmap): "a task explains the change" is replaced by evidence from
  the error, the test-repo commits and the API responses.

## Principles

- **Tracer bullets, not layers.** Every task is demoable end to end when it lands.
- **Two entry points, one pipeline.** The run chain is driven by the REST endpoint a CI step calls
  (by hand with `make trigger` until rollout); the analysis is also reachable from a CLI run from
  a laptop with personal tokens, e.g. `pitcrew analyze <run-url>`.
  Recorded Allure / GitLab responses become pytest fixtures, so the suite runs without network.
  Historical run links collected through the CLI are the backtest corpus of Stage 0.
- **Cheap before expensive.** Run-level checks, rerun and the static filters run before the
  agent; the agent gets one group of failures at a time, not the whole run.
- **Ground rules of the service** apply to the agent: MRs only, no weakened assertions, no
  deleted tests, no skips / retries; the diff is checked before the MR is published.

## Tasks

| Jira | Task | Demo when done | How it is tested | Blocked by |
|------|------|----------------|------------------|------------|
| [GW-3](https://stonfi.atlassian.net/browse/GW-3) | **Add the service to the run chain** | A CI step in `qa_automation` calls `POST /triggers` (environment, team, pipeline id, step `night_run` / `night_rerun`, Allure launch id; bearer token; `202`, work in the background). On `night_run` Pitcrew sorts the run into green (nothing to do), broken (pipeline failed before `test`, too few results against the nightly test plan, or too many failures — Slack Conclusion with the reason) or with failures: it writes the failed / broken tests into the team's rerun test plan and creates a `qa_automation` pipeline on it (same environment, `RUN_WITH_FLAGS`, `PITCREW_STEP=night_rerun`, launch tag linking it to the nightly launch). On `night_rerun` it checks the rerun the same way and posts a Conclusion: run and rerun links, flakes, consistently failing tests. Team config (YAML) and `service.env` land here; run chain state in the DB (SQLite locally, MySQL at deploy), idempotent by nightly pipeline id and step. Decisions: [CONTEXT.md](../CONTEXT.md), [ADR 0001](adr/0001-allure-testops-via-rest-api.md), [ADR 0002](adr/0002-rerun-as-gitlab-pipeline-with-ci-callback.md). | Locally: `make trigger` (curl) by hand after the nightly run and after the rerun; recorded TestOps / GitLab responses as fixtures; the CI step and the schedule variable come at rollout | — |
| [GW-4](https://stonfi.atlassian.net/browse/GW-4) | **Analyze model and schema errors** (static) | `pitcrew analyze <run-url>` reads the Allure results of the configured team, filters failures by model / schema error patterns, groups them, and posts (or prints, locally) a report: which tests, which models / schemas. Deterministic, no LLM. Reuses the team config and the TestOps client from GW-3; its result goes into the Conclusion. | Locally on real run links; fixtures | — |
| [GW-5](https://stonfi.atlassian.net/browse/GW-5) | **Set up Claude Code in the service deploy** | Claude Code runs inside the Pitcrew pod against LiteLLM, with its settings, sessions and model choice on persistent storage; a smoke task (read a file of the checked-out test repo and answer a question about it) works from the service. | Locally: Claude Code against LiteLLM from a laptop, `CLAUDE_CONFIG_DIR` on a local directory; the pod comes at rollout | LiteLLM token |
| [GW-6](https://stonfi.atlassian.net/browse/GW-6) | **Create MRs for model and schema errors** | For a group from GW-4: check out `qa_automation` at the run's commit, branch, hand the group to the agent, get the fix, check the diff against the ground rules, trigger a pipeline on the branch and wait for it, open a draft MR with the evidence and the pipeline result, post it to Slack. | Locally up to the push (dry run with the diff), then production | GW-4, GW-5 |
| [GW-7](https://stonfi.atlassian.net/browse/GW-7) | **Analyze and fix test-id errors** | Test-id failures are detected (static patterns, then the agent); the agent checks the real UI through Playwright CLI / MCP when the error alone is not enough; the fix goes through the same branch → pipeline → draft MR → Slack flow. | Locally + production | GW-6 |
| — | **Rollout (X)** | After the demo: security approval, Helm chart by DevOps, stage deploy, CI step in `qa_automation`; see [deploy-questions.md](deploy-questions.md). JSON logs from the start. | — | Demo |

**GW-3 status (2026-10-19).** The whole Run chain works locally: `night_run` (green /
broken with a Conclusion / Rerun started), `night_rerun` (the Rerun judged by the same rules
without the share of failures, then the Conclusion: Failed tests at night, the ones still failing
with their first error line, or a broken Rerun). Each chain has a trace id, answered to every
trigger, in every log line, and `GET /runs/{trace_id}` shows its status. Left for rollout: the CI
step in `qa_automation` that sends the triggers.

**Order.** GW-3 and GW-4 start now, both local. GW-5 as soon as the LiteLLM token
is there. Then GW-6, then GW-7. What comes after is decided once the drift flow has run
on real nights.

## Open questions to settle in the grilling of each task

- **GW-3:** settled in the grilling on 2026-10-14 — see the task row above, `CONTEXT.md`
  and ADRs 0001–0002. Still to confirm in the TestOps Swagger during `/to-spec`: the endpoints
  that update a test plan's test cases and list a launch's results by status.
- **GW-4:** the initial pattern set for model / schema errors (from real Allure error
  texts); grouping key (model / schema name vs. error signature); what the Slack report looks like.
- **GW-5:** settled in the grilling on 2026-10-22 — engine, configuration and what the
  Agent takes from the test repo in [ADR 0005](adr/0005-claude-agent-sdk-as-the-engine.md),
  terms in `CONTEXT.md` (Agent, Agent task, Working copy). LiteLLM speaks the Anthropic format
  with a bearer key (`ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`); model id and key in
  `service.env`. A persistent clone in `PITCREW_WORK_DIR` with a worktree per Agent task;
  `CLAUDE_CONFIG_DIR` under it. Read-only tools for the smoke, limits on turns, budget and time.
  The smoke is `pitcrew agent-smoke` (CLI, `make agent-smoke`), also run in the Docker image.
  Left for GW-6: linking the session to the Run chain and resuming it when a fix fails;
  masking what goes into the prompt (error texts from TestOps).
- **GW-6:** branch naming and MR attribution while the GitLab bot does not exist (personal
  token for now); how a pipeline is run on the fix branch for only the affected tests; the diff
  checks (no weakened assertions / deleted tests / skips / retries) and what happens when they
  fail; what "evidence" in the MR description is.
- **GW-7:** Playwright CLI vs. MCP from the pod; network access to the stage UI; login /
  test data for the UI check; how far the agent may go before handing over as "unsure".

## Process per task

Each Jira task is worked in a fresh session:

1. `/load-docs GW-<n>` — pull the Jira task.
2. `/grill-with-docs` — settle the open questions above; `CONTEXT.md` and ADRs grow here.
3. `/to-spec` — the spec issue in GitLab.
4. `/to-tickets` — tracer-bullet tickets with blocking edges, in the same context window.
5. `/implement #<ticket>` — one ticket per session, clear between tickets.
6. `/create-mr` — draft MR into master.

## Not in this round (direction)

- Environment / likely bug / unsure classes, the summary grouped by class and by team.
- Other teams as config entries; per-team Slack channels.
- Learning from merged MRs: diff what the human changed after Pitcrew's MR, read the review
  comments, keep notes that improve both the tests and Pitcrew's own fixes.
- Jira integration and service accounts, per the roadmap.
