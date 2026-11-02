# Pitcrew — Roadmap

Living document: extracted from the [concept and plan](concept-plan.md) and meant to be edited and extended as the project evolves.

Timelines are not fixed: moving to the next stage is decided by a gate, not a date. Stages 2+ are a direction, not a commitment.

## Stages

| # | Stage | Goal | Status |
| --- | --- | --- | --- |
| Init | Project initialization | Set up the repo for agent-assisted development and the Python / FastAPI service skeleton | In progress |
| 0 | Backtest | Collect the triage-time baseline and label historical Allure failures; measure classification accuracy offline | Planned |
| 1 | MVP: run analysis | Rerun failed tests, classify failures, post the morning summary; then enable drift-fix MRs (~2 months) | Planned |
| 2 | Library upgrades | Update outdated libraries in the test repo via MRs | Direction |
| 3 | Test generation | Generate tests from Jira tasks | Direction |
| 4 | TBD | | Direction |
| 5 | TBD | | Direction |

## Gates

| Gate | Between | Criteria |
| --- | --- | --- |
| G1 | Backtest → MVP | Classification accuracy on historical failures ≥ 80%; baseline collected |
| G2 | MVP report → MVP MRs | Classification accuracy confirmed on real runs |
| G3 | MVP → stage 2+ | Triage time < 30 min; MR acceptance ≥ 70%; team trusts the reports |

> Gate placement and criteria are a first draft derived from the metrics in the concept plan — refine as needed.

## Init — Project initialization

**Agent setup:**

- [x] `AGENTS.md` with project context, conventions, and ground rules.
- [x] `.claude/settings.json`: permissions and hooks.
- [x] Agent tooling carried over from the test repo and trimmed: `gitlab-mr`, `gitlab-issue`,
      `commit-message-format` skills; `commit-message` command;
      `skill-command-reviewer` agent; `codebase-memory-mcp` and `allure-testops` MCP servers.
- [x] Project-specific skills / commands as needed.

**Python / FastAPI setup:**

- [x] Project layout and `pyproject.toml` (`uv`, Python 3.13, `src/pitcrew/`).
- [x] FastAPI app skeleton with a temporary `GET /secret` endpoint to check secret delivery on deploy.
- [x] `GET /health` for deploy liveness probes.
- [x] Remove the temporary `GET /secret` and `APP_SECRET`: the service never returns a secret.
- [x] Service config separate from the agent's `.env`: environment variables, then the git-ignored
      `src/service.env` (template `src/service.env.example`, `make create-service-env`).
- [x] Linting, formatting, type checking (ruff, ty; ruff and gitlint run as pre-commit hooks).
- [x] Test setup (pytest).
- [x] Config via environment variables, `src/service.env.example`.
- [x] Dockerfile (multi-stage, non-root, config from environment variables).
- [x] GitLab CI pipeline: `lint` (ruff, ty, `uv.lock` check) and `test` (pytest, JUnit report in the MR).
- [x] Deploy questions settled with DevOps ([deploy-questions.md](deploy-questions.md)); deploy
      itself is deferred to the [Rollout](#rollout--after-the-mvp-demo) phase.

## Stage 0 — Backtest

Runs on the analysis CLI from Stage 1 (`pitcrew analyze <run-url>`, GW-4 in
[mvp-plan.md](mvp-plan.md)): historical runs collected through it are the backtest corpus, and
accuracy is measured once the agent-based analysis exists.

- [ ] Collect a 2–4 week baseline of triage time.
- [ ] Collect historical run links and label the failures: what each one actually turned out to be.
- [ ] Run classification against the labeled set and measure accuracy.

## Stage 1 — MVP

The task breakdown (Jira tasks under GW-1), order and per-task open questions live in
[mvp-plan.md](mvp-plan.md).

**Local first (decided 2026-10-13):** the MVP is built and run from a laptop with personal tokens and
exercised during the author's on-call. Deploy, CI integration and security approval are the Rollout
phase after the demo; nothing in Stage 1 waits for them.

**In scope** (one team — Gateway; another team is a config file):

- Automatic trigger when the nightly CI run completes; a run-level check that the run actually
  happened and is usable (jobs ran, test count, no shared setup failure) before anything else.
- Rerun of only the failed tests on the same environment, right after the run; flakes fall out of it.
- Test drift fixes via draft MRs: models and schemas first, then test-ids (with a UI check through
  Playwright). The fix is verified by a pipeline of `qa_automation` on the fix branch, never by
  running tests inside Pitcrew. Allure TestOps is the source of test results; GitLab is used for
  run status, reruns, the test repo and MRs.
- The engine is Claude Code inside the service, pointed at LiteLLM, reusing the agent tooling of
  `qa_automation`.
- Linking failures to test-repo commits since the last green run. Linking to current-sprint Jira
  tasks is deferred to a later step, pending approval of the Jira integration.

**Order:** run chain and the static model / schema analysis first, then Claude Code in the service,
then the MR flow for models / schemas, then test-ids.

**Landed:**

- [x] Run chain (GW-3), locally through `make trigger`: the Nightly run is checked, its
      Failed tests are rerun on the same Environment, and the Conclusion after the Rerun counts
      the tests still failing; a broken run or Rerun is reported as broken. The Conclusion is one
      Block Kit post: a header with Team and Environment, a block per run (Failed tests,
      pipeline, launch) and the reason or the count of the tests still failing (GW-4). One trace id per
      chain (`GET /run-chains/{trace_id}`, log lines). Each Run (the Nightly run, the Rerun) is
      its own record under the chain, listed by `GET /run-chains/{trace_id}` with its kind,
      pipeline, launch, expected size, Failed test count and Run outcome; one function judges
      every Run, the Run's kind choosing the rules, and the chain shows `judging_run` meanwhile
      (GW-5).
- [x] Model Error groups (GW-4, ADR 0004), behind the Team feature `error_groups`: the
      Failed tests of a Rerun that is not broken whose error a pydantic model raised are grouped
      by the model, stored with the Run chain, shown in `GET /run-chains/{trace_id}` and listed in the
      Conclusion (up to 10, largest first, each linking its test cases in TestOps); the rest are
      counted.
- [x] Claude Code in the service (GW-5, ADR 0005), locally through `make agent-smoke` and
      `make docker-agent-smoke`: the Agent runs through the Claude Agent SDK against LiteLLM in
      a Working copy of `qa_automation`, within a turn, a budget and a time limit. It loads the
      repo's CLAUDE.md files and skills, while the repo's Claude Code settings never reach its
      disk (a sparse worktree) and its tools, hooks, MCP servers and env are set by Pitcrew.
      Its prompt reaches the model with Pitcrew's secrets masked; stage test data is sent as is
      (ADR 0006).
- [x] Structured logs (ADR 0003): JSON on stdout for the cluster's log stack, console lines
      locally; every line of a request or a Step carries its context and the trace id; a Step
      that fails in the background is logged with what it was doing; secrets masked.

**After the drift flow is proven:**

- [ ] Environment / likely bug / unsure classes and the morning summary grouped by class.
- [ ] Replace personal tokens with service accounts: GitLab bot for `qa_automation` MRs, Allure TestOps, Jira.
- [ ] Jira integration (sprint tasks as drift evidence), if approved.
- [ ] Other teams as config entries; summary grouped by team.

**Out of scope:** test logic fixes and new checks, library upgrades (stage 2), test generation (stage 3), automatic bug filing.

## Rollout — after the MVP demo

Deferred from Init on 2026-10-13: a security approval is required before anything runs on stage, and
doing it first would stall the MVP. Details and DevOps answers in [deploy-questions.md](deploy-questions.md).

- [ ] Security approval after the demo.
- [ ] DevOps task: Helm chart with the whole configuration (secrets via the injector, network, S3, MySQL).
- [ ] Image build and push in CI; auto-deploy to stage on merge to master. The Agent runs in the
      arm64 image (`make docker-agent-smoke`); in the amd64 one it is not checked yet, because
      Claude Code segfaults under QEMU on an arm64 Mac: run the smoke on an amd64 host first.
- [ ] CI step in `qa_automation` that calls Pitcrew; shared secret.
- [ ] Security scans in CI (gitleaks, Trivy).

## Stage 2+ — Direction

- **Learning from merged MRs** — diff what the human changed after Pitcrew's MR, read the review
  comments, keep notes that improve both the tests and Pitcrew's own fixes.
- **Library upgrades** — a new role in the same service.
- **Test generation** from Jira tasks — reuses the harness understanding built for drift fixes.
- A role is extracted into a separate service only when it needs its own trigger, access, or scale.
