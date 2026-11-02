# agent/

The Agent: Claude Code run through the Claude Agent SDK against LiteLLM, in a Working copy of
the test repo (ADR 0005). Callers import from `pitcrew.agent`, which re-exports the public API.

| Module | Holds |
|--------|-------|
| `agent.py` | `Agent.run(AgentTask, working_copy)`: masks the prompt, builds the SDK options, reads the messages within the time limit, logs the start and the result |
| `task.py` | `AgentTask` and `AgentResult` |
| `constants.py` | `AgentAction` with its `ModelTier`, `AgentOutcome`, `READ_ONLY_TOOLS`, `SKILLS_DIR` |
| `environment.py` | `AgentEnvironment`: Claude Code's process env, built from `Settings` alone |
| `working_copy.py` | `WorkingCopies`: one persistent clone of the test repo, a sparse worktree per Agent task |
| `runner.py` | `AgentRunner`: the one SDK call |
| `exceptions.py` | `AgentNotConfiguredException`, `GitException` |

## Rules

- The test repo gives the knowledge, Pitcrew gives the rights (ADR 0005). The SDK options keep:
  exactly the task's tools, read-only by default; `Skill` approved one repo skill at a time and
  `can_use_tool` refusing whatever else reaches it; setting source `project` with `skills`
  naming the repo's skills, so Claude Code's bundled ones stay hidden; Pitcrew's `settings`
  with `disableAllHooks` and the LiteLLM URL; `strict_mcp_config`; the Working copy never marked
  trusted.
- A settings file Claude Code reads from the project goes into `EXCLUDED_FILES`: it stays absent
  on disk in every Working copy, not deleted for git.
- Claude Code's env comes only from `AgentEnvironment`: every variable of the service's env is
  blanked except `INHERITED_VARIABLES`, because the SDK merges the service's env, secrets and
  all, into Claude Code's. A variable Claude Code needs from the service's env goes into
  `INHERITED_VARIABLES`. Without `LITELLM_KEY` it fails before anything starts.
- The GitLab token reaches git only through the process env, never the remote URL or the git
  config on disk.
- The prompt is masked inside the Agent: `Agent.run` passes it through the log package's
  `masked` before it builds the SDK options and hands it to the runner, so no caller sends a
  prompt around it. Only the registered secrets (read through `Settings` or registered with
  `mask_secrets`) become `***`; a secret shorter than `MIN_SECRET_LENGTH` is not masked, the
  same as in logs. Test data is sent as is and nothing is put back into the answer (ADR 0006).
- A tool that brings external data into the Agent's context (an MCP server, a fetch) is not
  given to the Agent before the same masking covers what it returns.
- `runner.py` is the only module that calls the SDK.
- A new kind of Agent task is a new `AgentAction` member with its `ModelTier`;
  `Settings.agent.model` gives the model of the tier (`AGENT_MODEL_JUNIOR` / `_MIDDLE` /
  `_SENIOR`).
- Every Agent task is bounded by `AGENT_MAX_TURNS`, `AGENT_MAX_BUDGET_USD` and
  `AGENT_TIMEOUT_SECONDS`, and ends with an `AgentOutcome`.
- A Working copy is named by what it is for (`working_copies/smoke`): Claude Code keeps sessions
  by the path, so a resumed session is found there. Two tasks running at once never share a
  name; a stale Working copy of the same name is replaced.
- Tool calls and text are logged at `debug`, masked before being cut; the start and the result
  at `info`.
- No Step calls the Agent yet. The first one that does (GW-6) builds the Agent session of
  #43 first and calls the Agent only through it: one entry point hiding the Working copy, its
  name, the model of the tier and the limits, used by the CLI smoke too; a structured result
  (the SDK's `output_format`), never free text parsed; every Agent task recorded under the Run
  chain (model, cost, outcome, session id); the Working copy's diff checked against the ground
  rules by a deterministic module, outside the LLM. A Step never assembles `WorkingCopies` and
  `Agent` itself.
- `Agent.run` is synchronous (`anyio.run` inside): it cannot be called from async code. How a
  long Agent task runs in the background is decided with the Step executor (#32).

## Tests

`tests/test_agent/`, at the module's own seams: `AgentEnvironment` directly, `Agent` with a fake
`AgentRunner` on a plain directory, `WorkingCopies` against a local bare repo in `tmp_path`
standing in for GitLab. Never the real SDK or model.
