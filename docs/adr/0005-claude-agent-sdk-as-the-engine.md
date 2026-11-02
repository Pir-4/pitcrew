# Claude Agent SDK as the engine, configured only by Pitcrew

Pitcrew runs the Agent through the Python Claude Agent SDK (`claude-agent-sdk`), not by calling
`claude -p` itself. The SDK is the same Claude Code underneath: it ships the CLI binary in the
wheel (pinned by the package version) and drives it over stdio, so the Agent has Claude Code's
own tools to read, search and edit the Working copy and Pitcrew writes no repo tooling of its
own. What the SDK adds over a bare subprocess is the Python side we would otherwise write: typed
messages with the result, cost and session id, `can_use_tool` and hooks to hold the Agent to
the ground rules in code, and in-process tools.

The Agent is configured by Pitcrew alone:

- **Through the environment, from `Settings`.** The LiteLLM base URL, the bearer key
  (`ANTHROPIC_AUTH_TOKEN`) and the model come from the service env and are passed in the SDK
  options; no settings file holds a token. `CLAUDE_CONFIG_DIR` points into Pitcrew's working
  directory, so neither a developer's `~/.claude` nor a saved login ever reaches the Agent, and
  a laptop behaves like the pod.
- **Knowledge from the test repo, rules from Pitcrew.** The Agent reads `qa_automation`'s
  CLAUDE.md / AGENTS.md and skills, but never the repo's Claude Code settings: its tools,
  permissions, hooks, MCP servers and process env are set by Pitcrew per Agent task. The
  repo's settings are written for a human with credentials the service does not have. The
  exact setup, settled by the spike below:
  - The Working copy is a sparse worktree that leaves out `.claude/settings.json`,
    `.claude/settings.local.json` and `.mcp.json`: `git worktree add --no-checkout`, then
    `git sparse-checkout set --no-cone '/*' '!/.claude/settings.json'
    '!/.claude/settings.local.json' '!/.mcp.json'` and the checkout of the ref, with
    `extensions.worktreeConfig` on in the clone so the sparse setting stays in that worktree
    and the clone and the other Working copies stay whole. The files are absent on disk but
    not deleted for git: `git status` is clean and a commit of the Agent's fix cannot remove
    them.
  - Setting source `project`: the root CLAUDE.md, a module's CLAUDE.md when the Agent reads a
    file inside it (in `qa_automation` every CLAUDE.md is a symlink to the AGENTS.md beside
    it, so that is what the Agent reads), `.claude/skills`, `.claude/agents` and
    `.claude/commands`.
  - Pitcrew's own settings in the SDK's `settings` (the flag layer, above `project`):
    `disableAllHooks` and an `env` that repeats the LiteLLM URL, so even a settings file that
    slipped into the Working copy cannot change them.
  - `tools` lists exactly the Agent task's tools (read-only: `Read`, `Grep`, `Glob`, `Skill`);
    `allowed_tools` the ones approved without asking; `skills` the names under the repo's
    `.claude/skills`, so the skills bundled with Claude Code are hidden; `strict_mcp_config`;
    `can_use_tool` refuses whatever reaches it.
  - The Working copy is never marked trusted in `CLAUDE_CONFIG_DIR` (`hasTrustDialogAccepted`).
  - Pitcrew's own `PreToolUse` callbacks in the SDK still run under `disableAllHooks`; they,
    not `can_use_tool`, are where GW-6 gates every call, because Claude Code approves
    read-only Bash commands (`git status`, `ls`, `echo`) itself without asking `can_use_tool`.
- **Git and GitLab belong to Pitcrew.** Pitcrew clones, fetches, creates the Working copy and,
  later, pushes and opens the MR after checking the diff; the Agent works only inside the
  Working copy it is given.

## Considered Options

- `claude -p` as a subprocess: the same engine, but we would install and pin the CLI in the
  image ourselves, parse `stream-json` ourselves and could gate tools only through hooks or a
  permission-prompt tool.
- Setting source `project` on a whole Working copy, with Pitcrew's settings on top (the plan
  before the spike): holds for hooks and tools, but the repo's `env` still applies.
- Nothing loaded from disk (`setting_sources=[]`) with the repo's AGENTS.md put into the system
  prompt: safe, but loses the skills and the module CLAUDE.md files that load as the Agent reads.
  Kept as the fallback should a Claude Code update start reading settings from elsewhere.

## The spike (GW-5, 2026-10-28)

Run on a fresh clone of `qa_automation` (`48f255b59`) with `claude-agent-sdk` 0.2.174 (Claude
Code 2.1.310), a new `CLAUDE_CONFIG_DIR` for each Agent task, against a local stub of the
Messages API that recorded every request and replayed scripted tool calls, then against LiteLLM
(`claude-haiku-5-5`) asking the Agent directly. On a whole Working copy, with setting source
`project`:

- **Hooks.** The repo's `SessionStart` and `PreToolUse` hooks run (the guard denied a command with
  `glab api --method DELETE` in it); with `disableAllHooks` in Pitcrew's settings they do not.
  Pitcrew's SDK `PreToolUse` callback is called either way.
- **Allow rules.** In a Working copy never marked trusted, Claude Code ignores the repo's 82
  allow rules and says so on stderr; its deny rules still apply. Once it is marked trusted,
  `Edit(docs/**/*)` approved an `Edit` that Pitcrew's `allowed_tools` did not list, without
  asking `can_use_tool`. A tool left out of `tools` is unavailable whatever the rules or a
  skill's `allowed-tools` say ("No such tool available").
- **Process env.** The repo's `env` applies even untrusted and overrides the process
  env Pitcrew passes: a planted `ANTHROPIC_BASE_URL` sent the request, with the key,
  to another server. An `env` in Pitcrew's settings wins for the keys it names, but cannot
  name every key that matters (`NODE_OPTIONS`, proxies). This is what rules out the
  whole Working copy. The repo's `model` did not win over the model Pitcrew passes.
- **MCP.** `.mcp.json` with `enabledMcpjsonServers` starts the repo's servers
  (`codebase-memory-mcp` connected, `dbhub` was starting `uv run dbhub-mcp`) unless
  `strict_mcp_config` is set.
- **Knowledge.** The root CLAUDE.md goes into the first message; `tests/CLAUDE.md` arrived when
  the Agent read inside `tests/`; with the `Skill` tool the repo's 15 skills are listed and run
  (`test-conventions` was invoked). Claude Code's bundled skills are listed too unless
  `skills` names the repo's. Without the `Skill` tool the skills are not listed at all.

In the sparse Working copy the same Agent task with none of Pitcrew's overrides loaded no hooks, no
MCP servers and no allow rules, and still had CLAUDE.md, the skills and the agents. Through
LiteLLM the Agent answered that it had the two CLAUDE.md files, the 15 repo skills, the tools
`Glob`, `Grep`, `Read` and `Skill`, and no hooks or MCP servers.

**What the repo's `.claude/` holds:** `settings.json` with 82
allow rules (git, `uv run pytest`, `glab`, `Edit(docs/**/*)`, the `dbhub` SQL tools), deny
rules (`rm`, `sudo`, `.env` and token files) and ask rules; a `SessionStart` hook that warns
about missing tools and runs `glab auth login` with `GITLAB_TOKEN` from `.env`, and a
`PreToolUse` guard on `glab api`; `.mcp.json` with `codebase-memory-mcp` (a binary in
`~/.local/bin`), `allure-testops` (`ALLURE_TOKEN` from `.env`) and `dbhub` (DB tunnels). Of the
15 skills, `gitlab-issue`, `gitlab-mr`, `log-improvement` (glab), `db-query` (dbhub), `kafka-cli`
(Kafka), `playwright-cli` (the `playwright-cli` binary), `describe-module` and
`sync-module-docs` (the code graph, glab) need a credential or a tool the service lacks; the
rest read the repo. Also 6 agents and 8 commands, unused while `Agent` is not among the tools.

## Consequences

- Updating Claude Code means updating the `claude-agent-sdk` package; the spike's checks are
  worth repeating then, since what loads from the project is Claude Code's behaviour, not ours.
- Pitcrew's code that creates the Working copy owns the sparse exclusions; a new Claude Code
  settings file in the project (another name, another place) goes into them.
- A skill whose `allowed-tools` asks for more than the Agent task's tools fails at the tool
  call, not before; the Agent reports it like any refused call.
