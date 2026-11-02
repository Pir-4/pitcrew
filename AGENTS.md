# AGENTS.md

Guidance for coding agents working in this repository.

## What Pitcrew is

An AI service that takes over the routine after the nightly e2e test run of the API, the test repo
`gateway/qa_automation` owned by QA: reruns failed tests, filters out flakes, classifies real failures
(flake / environment / test drift / likely bug / unsure), highlights likely bugs, and proposes
test fixes via MRs. Read `README.md`, then `docs/concept-plan.md` and `docs/roadmap.md` before
touching anything else — they are the source of truth for scope and ground rules.

**Status:** Init stage. The Python / FastAPI skeleton is in place (`src/pitcrew/`, `GET /health`
for liveness probes) with a Dockerfile and a GitLab CI pipeline (`lint` and `test` jobs; `test`
fails below the coverage floor in `pyproject.toml`). The Run chain (GW-3) is in place end to
end: `POST /triggers` records a Run chain per Nightly run under a trace id, checks the Allure
launch belongs to the pipeline and reads its Failed tests from TestOps; a broken Nightly run
(pipeline stopped before `test`, too few results, too many failures) gets a Conclusion in the
Team's Slack channel instead of a Rerun; with failures, writes them into the Team's Rerun test
plan and creates the Rerun pipeline in GitLab. The Rerun's `night_rerun` trigger checks the Rerun
by the same rules (without the share of failures) and posts the Conclusion: how many tests still
fail, or why the Rerun is broken. With the Team feature `error_groups`, a Rerun that is not broken
has its Error groups recognized (the model Error kind, ADR 0004), stored with the Run chain and
listed in the Conclusion. Every Conclusion is one Block Kit post with a block per Run, built by
one pure function from the Runs' stored outcomes and posted by the Publisher, which keeps each
Slack post as its own record under the chain. Every trigger is answered with the trace id;
`GET /run-chains/{trace_id}` shows the status of the whole chain and lists its Runs (each Run, the
Nightly run or the Rerun, is its own record under the chain). A Step that fails is logged once and
leaves the chain in the `failed` activity with its `failure_reason` (the error, masked and cut
short); the same trigger again (`202`) runs the Step from its start and clears it. The Agent runs
through the Claude Agent SDK against LiteLLM: `make agent-smoke` asks it about `qa_automation` in
a Working copy, read-only, with the repo's knowledge (CLAUDE.md files and skills) but only
Pitcrew's rights (the repo's Claude Code settings never reach the Working copy; tools, hooks, MCP
servers and env are Pitcrew's, ADR 0005), its prompt masked for secrets (ADR 0006), within a turn,
a budget and a time limit, and exits non-zero naming the limit it hit; `make docker-agent-smoke`
does the same in the service's Docker image. Deploy and secret delivery are not decided yet.
`docs/roadmap.md` lists what the Init stage must produce. Keep it updated when something lands.

**Ground rules the service itself must follow** (and therefore any code written here):
- Never pushes to the main branch of the test repo — only MRs reviewed by a human.
- Never weakens assertions, deletes tests, or adds skips/retries.
- Every decision comes with an explanation and links.
- Secrets are masked before anything reaches the LLM; stage test data is sent as is (ADR 0006).

## Stack

Python 3.13, FastAPI, `uv` for dependencies, pytest, ruff, ty, Docker, GitLab CI.
LLM access only through the internal LiteLLM (Claude via AWS Bedrock).

Layout: `src/pitcrew/` (app and startup in `main.py`), tests in `tests/`. One subpackage per
concern; each holds an `AGENTS.md` with its modules and its rules. A change that adds a module,
a rule or a way of doing things there updates that file in the same change.

| Package | Concern |
|---------|---------|
| `config/` | Service settings from the env and the Team configs |
| `api/` | HTTP only: `POST /triggers`, `GET /run-chains/{trace_id}`, auth, request logging, the exception handlers that turn a rejection into its HTTP answer |
| `steps/` | The Steps of the Run chain and the domain rules they apply |
| `clients/` | One client per external service: TestOps, GitLab, Slack; `WebLinks`, the links to their web pages |
| `agent/` | The Agent: Claude Code through the Claude Agent SDK in a Working copy (ADR 0005) |
| `db/` | Run chain state: `models/`, the domain model (entities, their transitions, their value types, status columns typed by their enums); repositories and services, storage only; Alembic migrations |
| `log/` | The logging setup (ADR 0003); how to log is in **Logging** below |

Outside the subpackages:
- `constants.py` — domain constants shared by the API, the clients and the Steps (`Step`,
  `Environment` as `qa_automation` spells its input, GitLab `JobStatus`, Allure
  `TestStatus`, `FAILED_STATUSES`, the Agent's `ModelTier`). No Team is listed in the code: a
  Team is any name with a Team config (`config/`).
- `cli.py` — the `pitcrew` console script (`[project.scripts]`, `argparse`): `agent-smoke`.
  Logs go to stderr, the answer to stdout; a message for the developer running it (no key, no
  such Team) is printed to stderr. Tested through `main(argv, runner=...)` in
  `tests/test_cli.py`.

Across the packages:
- Imports go one way: `api/` → `steps/` → `db/models/`, `clients/`, `config/`. `db/` imports
  only `constants.py`; `clients/` only `config/settings.py`, `log/` and `constants.py`;
  `agent/` only `config/settings.py`, `log/` and `constants.py`; nothing imports `api/`.
  `log/` and `constants.py` import nothing of Pitcrew's. A value type of the domain lives in
  `db/models/` (there is no separate domain package).
- A package `AGENTS.md` is the map of its modules and the rules a change must keep. It never
  retells what a docstring already says (a transition's branches, a function's steps): it
  names the function and the rule, so that a change of behaviour is made in one place.
- A seam (a `Protocol`, a fake behind it) exists only where a test cannot reach otherwise:
  the `httpx` transport of the clients and `AgentRunner` for the SDK. No `Protocol` for a
  single adapter.
- Where a growth of the Run chain goes, so that nothing is copied: a new kind of Run is a
  `RunKind` member and its branch in `judge_run` (no new columns, no copy of the scenario,
  `steps/AGENTS.md`); a new Slack post is a `PostKind` posted through the `Publisher`; a new
  rejection is a domain exception plus its handler in `api/exception_handlers.py`; a new
  external service is a client, its settings group and a field of `StepDependencies`; a
  Step calling the Agent goes through the Agent session (#43, `agent/AGENTS.md`); background
  work runs through `BaseStep.run` until the Step executor (#32) replaces `BackgroundTasks`.

Tests are laid out by seam; read `tests/AGENTS.md` (the layout and the rules of writing a test)
and `tests/support/AGENTS.md` (the shared test code) before writing one. Each subpackage's
`AGENTS.md` names where its tests live. Never the real SDK or model in a test.
Add dependencies with `uv add` (`--dev` for tooling), never by editing `pyproject.toml` by hand.

## Comments and docstrings

Code says what it does through names, types and structure. A `#` comment says **why**, and only
where the obvious approach was tried and did not work, or where the code works around a library,
an external service or a security constraint: name the reason, so that nobody "simplifies" the
code back. Everywhere else, rename or extract until the code reads without one.

Docstrings document the interface, Google style:
- Every public module, class and function has a docstring: what it is for, and the rules a
  caller must know that the signature cannot carry (ordering, idempotency, side effects).
- `Args:` describes each parameter of a public function or method, `Returns:` the result when
  the name does not say it, `Raises:` the exceptions a caller handles.
- `Attributes:` in the class docstring describes the fields of a dataclass, an ORM model or a
  config model, and the members of an enum, whose meaning the name does not carry. A field of an
  API schema uses `Field(description=...)` instead, so that OpenAPI shows it.
- A constructor's parameters go into `Args:` of the `__init__` docstring.
- What a library defines, the library documents: an override of its hook (`model_post_init`,
  `settings_customise_sources`, a structlog processor, `logging.Formatter.format`, an ASGI
  middleware's `__init__`), a FastAPI endpoint or dependency take no `Args:`. An endpoint's
  docstring is its OpenAPI description, written for the caller of the API.

## Logging

How and why: `docs/adr/0003-structured-logging.md`. One setup for the whole process; JSON on
stdout at deploy, console lines with `make run`; `LOG_LEVEL` / `LOG_FORMAT` in the service env.

- Get a logger with `logger = get_logger(__name__)` from `pitcrew.log`; never `logging.getLogger`,
  `print`, or a handler of your own.
- A message is a short constant phrase; the data goes in fields:
  `logger.info("Rerun started", rerun_pipeline_id=..., test_case_count=...)`, never
  `f"Rerun {id} started"` or `%s`. Field names are `snake_case`, ids are plain values.
- Do not pass context by hand. A request has `request_id` and the trigger's fields; `accept`
  binds `trace_id`; a Step's `run` opens a scope with the Run chain's context; `_doing` binds
  `activity`. New context of the same kind goes in with `bind_log_context(...)` (the current
  scope) or `log_scope(...)` (new work, e.g. a new background task).
- Levels: `debug` details for local digging; `info` the events of a Run chain (trigger accepted,
  Step started / finished, Run outcome, Conclusion, Rerun, each external call); `warning` a
  rejected trigger or an error answer a caller may handle; `error` what nobody handles (a Step
  failed, a `5xx` request). `logger.exception(...)` inside `except` adds the traceback.
- A background Step catches nothing itself: `BaseStep.run` logs its failure once, records the
  `failed` activity with its masked reason in a fresh session, and ends.
- A secret read through `Settings` (a field or `Settings.secret`) is masked in every line; a
  secret from anywhere else must be registered with `mask_secrets`. Text cut short for a log
  line goes through `masked` first, so that no part of a secret survives the cut. Never log a header, a request
  body sent to an external service, or a webhook URL.
- An external process (a future Claude Code CLI run) does not inherit stdout: read its output
  line by line and log each line within the Run chain's scope, so it carries the trace id and is
  masked.
- A test asserts on what is logged through the `logs` fixture, including that no secret appears.

## Branching and commits

- Main branch: `master`. Branch name: `{JIRA-ID}_{summary}` or `{lastname}/{JIRA-ID}_{summary}`
  (enforced by pre-commit).
- Commit message: `<JIRA-ID>: <Summary>` title plus a bullet body, no trailers — load the
  `commit-message-format` skill before writing any commit message (gitlint enforces the title).
- No AI attribution anywhere: no `Co-Authored-By` trailer in commits and no "🤖 Generated with
  Claude Code" (or any other AI footer) in MR titles or descriptions. This overrides the
  assistant's default attribution. Add one only when the user asks for it.
- `git add` every new file meant to be part of the change right after creating it, except files
  matched by `.gitignore`. Never `git add -f` an ignored file.

## Agent tooling (`.claude/`)

| Item | Purpose |
|------|---------|
| `settings.json` | Permissions (allow / deny / ask) and hooks. Rules are prefix-matched, evaluated deny → ask → allow |
| `hooks/session_start.sh` | Warns about missing tools and `.env` values; logs `glab` in from `GITLAB_TOKEN` |
| `hooks/bash_guard.sh` | Enforced in every mode, auto included: denies force-push, push to master/main and `--no-verify`; denies shell reads of `.env` and `src/service.env`; denies `glab api` DELETE and MR approve/merge, asks on any other `glab api` write |
| `skills/gitlab-mr` | Read MRs, diffs, review threads; post draft notes after explicit approval |
| `skills/gitlab-issue` | Search / view / create / update issues of this project; writes only after "publish" |
| `skills/commit-message-format` | The commit message contract |
| `skills/create-mr` | `/create-mr`: push the branch and open a draft MR into master; title and `## Changes` come from `/commit-message --branch`, `## Issues` (`Closes #N` for an issue the MR finishes, `Related to #N` otherwise) from the issues it works on, the rest from `.gitlab/merge_request_templates/default.md`; runs only after "publish" |
| `commands/commit-message` | Generate a commit message for staged / branch / specific files |
| `commands/load-docs` | Download a Jira issue (with comments, parent, children) and Confluence pages into `docs/Product/` (git-ignored) and write `_CONTEXT.md` for the task |
| `agents/skill-command-reviewer` | Reviews changes to skills, commands, settings, hooks, Makefile, `.mcp.json` |

MCP servers (`.mcp.json`): `codebase-memory-mcp` (code graph — use it first for code
exploration) and `allure-testops` (Allure TestOps API, needs `ALLURE_TOKEN` in `.env`).

Plugin `mattpocock-skills@claude-plugins-official` (enabled for the team in `settings.json`,
`make install-matt-pocock-skills`): `/grill-me`, `/grill-with-docs`, `/to-spec`, `/to-tickets`,
`/tdd`, `/triage`, `/code-review` and the rest of Matt Pocock's engineering skills. Its repo
config lives in `docs/agents/` (issue tracker = GitLab via `glab`), `CONTEXT.md` and `docs/adr/`,
all committed. Writes to GitLab go through the same `ask` permissions as every other `glab` call.

Secrets of the agent tooling live in `.env` (`make create-env`, template in `.env.example`);
secrets of the service live in `src/service.env` (`make create-service-env`, template in
`src/service.env.example`, one commented line per variable — add yours there when a feature needs
a new one). It sits under `src/` because it belongs to the application, not to the repo tooling.
Both are git-ignored. Never read `.env` or `src/service.env`; hooks, tools and the service load
what they need themselves.

## Makefile

| Task | Command |
|------|---------|
| Fresh clone: install uv, `uv sync`, install pre-commit + commit-msg hooks | `make setup` |
| Create `.env` interactively | `make create-env` |
| Create `src/service.env` (service config) interactively from `src/service.env.example` | `make create-service-env` |
| Install agent tooling (node, ripgrep, jq, glab, codebase-memory-mcp, mattpocock-skills plugin, atlassian-extractors) | `make install-ai-tools` |
| Run the service locally with reload (Swagger at `/docs`) | `make run` |
| Send a Run chain trigger to the local service (token from `src/service.env`); prints the trace id | `make trigger STEP=night_run\|night_rerun PIPELINE=... LAUNCH=... [TEAM=Gateway ENV=staging]` |
| Show the status of a Run chain from the local service | `make run-status TRACE=...` |
| Ask the Agent about `qa_automation` in a Working copy and print its answer (needs `LITELLM_KEY`) | `make agent-smoke [REF=... PROMPT="..." TEAM=Gateway]` |
| Tests | `make test` |
| Tests with line and branch coverage (`pytest-cov`); fails below `fail_under` in `pyproject.toml`, as the CI `test` job does | `make coverage` |
| Lint + format check / auto-fix / format only | `make lint` / `make fix` / `make format` |
| Type check (ty) | `make typecheck` |
| Check `uv.lock` is up to date | `make lock-check` |
| Install Colima + docker CLI + buildx (macOS, once) | `make install-colima` |
| Start Colima (adds the corporate proxy CA to the VM) / stop it | `make colima-start` / `make colima-stop` |
| Start Colima, build the image, run it on :8000 (`src/service.env` goes in as environment variables when present, `var/docker-workspace` is mounted as `PITCREW_WORK_DIR`) | `make docker-up` |
| Build the Docker image / run it (`DOCKER_PLATFORM=linux/amd64` for the CI architecture) | `make docker-build` / `make docker-run` |
| `make agent-smoke` in a container of the image, with the Working copy in the mounted `var/docker-workspace` (amd64 under QEMU on an arm64 Mac segfaults: see README) | `make docker-agent-smoke [REF=... PROMPT="..." TEAM=Gateway DOCKER_PLATFORM=linux/amd64]` |

Before finishing a change, run `make lint typecheck test`.

## Library questions

Do not answer from memory about a dependency's behaviour. Once `pyproject.toml` exists, read the
installed source under `.venv/` first; web search last, and only for public libraries.

## Agent skills

### Issue tracker

Jira (GW) is the read-only input; GitLab issues of this repo are the agent's work buffer. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary plus `improvement` for out-of-scope follow-ups. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
