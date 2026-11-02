# Issue tracker: Jira in, GitLab issues as the agent's buffer

## Jira — the source, read-only

Work starts from a Jira task (`GW-<n>`). The human owns Jira: creates, edits and moves tasks.
The agent never writes to Jira.

- **Pull context**: `/load-docs GW-<n>` (or with no argument — the key comes from the branch).
  It downloads the issue with comments, its parent and children, linked Confluence pages into
  `docs/Product/` (git-ignored) and writes `docs/Product/jira/GW-<n>/_CONTEXT.md`. Read that first.
- **Refresh**: `/load-docs --refresh` when the human says the Jira task changed.
- A Jira task is not an issue in this tracker. Skills that say "fetch the relevant ticket" mean
  a GitLab issue; the Jira task is the background they cite.

## GitLab issues — the agent's work buffer

Specs, tickets and triage live as GitLab issues of `valentin.agapitov/pitcrew`, worked with
[`glab`](https://gitlab.com/gitlab-org/cli). Every issue the agent creates names its source on the
first line of the description: `Source: GW-<n> (https://stonfi.atlassian.net/browse/GW-<n>)`.

### Conventions

- **Create**: `glab issue create --yes --no-editor --title "..." --description "$(cat <file>)"`. Write the body to a scratch file first.
- **Read**: `glab issue view <number> --comments`; `--output json` for machine-readable output.
- **List**: `glab issue list --output json -P 100` with `--label` filters.
- **Comment**: `glab issue note <number> --message "..."` (GitLab calls comments "notes").
- **Labels**: `glab issue update <number> --label "..."` / `--unlabel "..."`.
- **Close**: post the reason with `glab issue note` first, then `glab issue close <number>` (close takes no comment).
- **Merge requests**: `glab mr create`, `glab mr view`, `glab mr note` — same shape as `gh pr` with `mr` and `note`/`--message`.

Every write (create, note, update, close) is shown to the human as a draft first and runs only after
they say **publish** — the same gate as the `gitlab-issue` skill.

## Merge requests as a triage surface

**MRs as a request surface: no.**

## When a skill says "publish to the issue tracker"

Create a GitLab issue (with the `Source: GW-<n>` line).

## When a skill says "fetch the relevant ticket"

Run `glab issue view <number> --comments`. If it cites a GW task and `docs/Product/jira/GW-<n>/_CONTEXT.md` is missing, run `/load-docs GW-<n>` first.

## When work surfaces something out of scope

Do not do it in the current change. Log it as an `improvement` issue — see the rules in
`docs/agents/triage-labels.md` (Project labels).

## Wayfinding operations

Used by `/wayfinder`. The **map** is one issue; **child** issues are tickets.

- **Map**: an issue labelled `wayfinder:map` (Notes / Decisions-so-far / Fog). `glab issue create --label wayfinder:map`.
- **Child ticket**: `Part of #<map>` at the top of the description, label `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`).
- **Blocking**: native link via a note `glab issue note <child> --message "/blocked_by #<blocker>"` (Premium/Ultimate). Where unavailable, a `Blocked by: #<n>, #<n>` line at the top of the description.
- **Frontier query**: `glab issue list --output json -P 100` over the map's children; drop any with an open blocker — check native links with `glab api "projects/:fullpath/issues/<child-iid>/links"` (substitute the iid) and the `Blocked by` line — or an assignee. First in map order wins.
- **Claim**: `glab issue update <n> --assignee @me`.
- **Resolve**: `glab issue note <n> --message "<answer>"`, then `glab issue close <n>`, then add a gist + link to the map's Decisions-so-far.
