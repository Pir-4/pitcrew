# Pitcrew

AI service that takes over the routine after the nightly test run: reruns failed tests, filters out flakes, classifies real failures, highlights likely bugs, and proposes test fixes via MRs. By morning, the team gets an analyzed run instead of a list of red tests.

Written by a backend developer of the Gateway team (the API of a DEX on TON, for the frontend and the integrators), whose nightly e2e run (`qa_automation`, owned by QA) used to cost someone the first hours of every morning. One team for now; another team is a config file.

> **Status:** Init stage, not deployed yet. The Run chain works end to end: the nightly trigger, the rerun of failed tests, the Slack summary and the error groups of what still fails. The AI Agent runs read-only through a smoke command; classification and fix MRs are next. See [roadmap](docs/roadmap.md).

## How it works

1. Triggered when the nightly CI run completes.
2. Reruns only the failed tests on the same environment, while it is still free.
3. Classifies each remaining failure: **flake**, **environment**, **test drift**, **likely bug**, or **unsure** — with an explanation and links (Allure, logs, sprint tasks).
4. Opens MRs for test drift only (test-ids, locators; schemas/models only when a current-sprint task explains the change).
5. Posts a morning summary to the team channel, grouped by class.

## Ground rules

- Never pushes to the main branch — only MRs reviewed by a human.
- Never weakens assertions, deletes tests, or adds skips/retries.
- Every decision comes with an explanation and links.
- Secrets are masked before anything reaches the LLM; stage test data is sent as is (ADR 0006).

## Integrations

CI · Allure · Jira (read-only) · LiteLLM (Claude via AWS Bedrock) · team chat

## Development

```sh
make setup                # uv, Python 3.13, dependencies, git hooks (ruff, gitlint)
make create-env           # .env with the agent tooling's tokens
make create-service-env   # src/service.env, the service's own config (template src/service.env.example)
make run                  # http://127.0.0.1:8000/docs
make trigger STEP=night_run PIPELINE=... LAUNCH=...   # POST /triggers, prints the trace id
make run-status TRACE=... # GET /run-chains/{trace_id}: the chain's status, its Runs, the Conclusion
make lint typecheck test

```

### Docker (macOS, via Colima)

```sh
make install-colima   # once: colima, docker CLI, buildx
make docker-up        # start Colima, build the image, run it on http://127.0.0.1:8000 (Ctrl+C stops)
make colima-stop      # stop the Colima VM when done
```

The service reads its config from environment variables, then from `src/service.env`; the root
`.env` belongs to the agent tooling and is never read by the service. `docker-run` passes
`src/service.env` into the container as environment variables when it exists, the way Helm injects
them at deploy. On the corporate network `docker-up`
also adds the corporate proxy root CA to the Colima VM, otherwise image pulls fail with
`x509: certificate signed by unknown authority`. Separate steps: `make colima-start`,
`make docker-build`, `make docker-run`.

`make docker-agent-smoke [REF=... PROMPT="..."]` runs `make agent-smoke` in a container of the
image: its `git`, its non-root user and the Claude Code binary bundled in the SDK wheel. The
container's `PITCREW_WORK_DIR` (the clone of `qa_automation`, the Working copies, the Agent's
Claude state) is `var/docker-workspace` on the host, mounted by `docker-run` as well; on a Linux
host it must be writable by uid 1000. `DOCKER_PLATFORM=linux/amd64` builds and runs the
architecture the CI build will produce. On an arm64 Mac it is emulated by QEMU, and there the
bundled Claude Code segfaults as soon as a session starts (`--version` still works), so the amd64
image is checked on an amd64 host, or in Colima started with Rosetta (`colima start --vz-rosetta`).

## Docs

- [Concept and plan](docs/concept-plan.md)
- [Roadmap](docs/roadmap.md)
- [MVP plan](docs/mvp-plan.md)
