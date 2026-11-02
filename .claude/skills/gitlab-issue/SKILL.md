---
name: gitlab-issue
description: Access GitLab Issues of valentin.agapitov/pitcrew — search, view, create, update (title, description, labels), comment, close, reopen. Use when the user asks to find, log, update or comment on an issue, or when another skill needs an issue created and its `#<iid>` returned. Never deletes an issue.
allowed-tools: Write, Bash(rg *), Bash(glab issue list*), Bash(glab issue view*), Bash(glab issue create*), Bash(glab issue update*), Bash(glab issue note*), Bash(glab issue close*), Bash(glab issue reopen*), Bash(glab api "projects/*)
model: haiku
---

# GitLab Issues with glab CLI

## Repository

This skill operates exclusively on:
- **Host:** `gitlab.ston.fi`
- **Project:** `valentin.agapitov/pitcrew` (id 1269)
- **Encoded path:** `valentin.agapitov%2Fpitcrew`

Credentials are persisted via `glab auth login` — the `SessionStart` hook logs in from `.env`.
Never read `.env` yourself. `:fullpath` in `glab api` URLs resolves to the current repo.

## Rules — never violate

- **Never** run `glab issue delete` *(denied in project settings)* and never pass `-R` / `--repo`
  pointing at another project.
- **Never** use `glab api` with the DELETE, PUT or PATCH method. Every change goes through
  `glab issue update` / `close` / `reopen` / `note` — they cover everything this skill does.
  The `PreToolUse` guard (`.claude/hooks/bash_guard.sh`) denies DELETE and asks on every other `glab api` write; do not try to get around it.
- **Create, comment and update only after "publish".** Same discipline as MR draft notes:
  print the full draft as text — title, the whole body in a fenced block, the exact labels,
  assignee — as the last thing in the message and end the turn. The user replies **publish**
  (or the same in their language); only then run the command. Never ask for that
  confirmation through an AskUserQuestion popup (it hides the text). A bare "yes" is not
  "publish", before or after the draft — reply with the draft and the publish line again.
  Any change → print the whole draft again and wait again.
- **Never invent labels.** GitLab may silently create an unknown label on `create`/`update`.
  Check the label list first (see *Labels*) and use only names that exist; if the caller wants
  a new label, say so and stop.
- **Always** pass `--yes --no-editor` to `glab issue create`. The Bash tool has no TTY: glab's
  own editor and confirmation prompt cannot be answered there and the command hangs. The
  safety gates are the user's "publish" in the conversation and the `ask` permission on
  `glab issue create` — not glab's prompt.
- **Never** use `--web`; never set `--confidential` unless the user asks.
- **Always end** with the issue reference on its own line: `#<iid> <web_url>` — callers
  (other skills, module docs) paste exactly that.

## Workflow: create an issue

1. Search first (below) — if a similar open issue exists, offer "comment on #N instead".
2. Write the body to a temp file in the session scratchpad (Markdown, multi-line is fine).
3. Print the draft: title, body in a fenced block, labels, assignee. End the turn; wait for
   **publish**.
4. Create:
   ```bash
   glab issue create --yes --no-editor -t "<title>" -l "label-a,label-b" -d "$(cat <scratch-file>)"
   ```
   Optional: `-a <username>` assignee, `--linked-mr <mr-iid>`.
5. `create` prints the issue URL; its last path segment is the iid. Print `#<iid> <web_url>`
   (or read both from `glab issue view <iid> --output json`).

## Workflow: create several issues at once (batch — one approval for all)

Used when a flow needs several issues at once. The point is ONE Bash command for the whole
batch, so the human confirms once: every `glab api` write (POST, `--input`, `--field`) is gated by
`.claude/hooks/bash_guard.sh`, which asks per Bash call, not per issue. One `glab issue create`
per issue would cost a confirmation each.

1. Search first, per issue (below).
2. With the **Write tool** (not a shell heredoc) write one JSON file per issue into the
   session scratchpad: `{"title": "…", "description": "<the shown body>", "labels": "a,b,c"}`.
3. Print all drafts, end the turn, wait for **publish**.
4. Create the batch in ONE command — plain literals only, chained with `&&`:
   ```bash
   glab api "projects/1269/issues" --method POST --header "Content-Type: application/json" --input <scratch>/i1.json | rg -o '"iid":[0-9]+|"web_url":"[^"]+"' && \
   glab api "projects/1269/issues" --method POST --header "Content-Type: application/json" --input <scratch>/i2.json | rg -o '"iid":[0-9]+|"web_url":"[^"]+"' && \
   glab api "projects/1269/issues" --method POST --header "Content-Type: application/json" --input <scratch>/i3.json | rg -o '"iid":[0-9]+|"web_url":"[^"]+"'
   ```
   Cross-links between the new issues go in a second single command, same shape:
   `glab api "projects/1269/issues/<iid>/notes" --method POST --field body="Related: #N — <why>"`.
5. Print `#<iid> <web_url>` for each. Spell every path and iid out — no `$(…)` or loop
   variables inside the `glab` command, so the human sees exactly what runs.

POST is the only method this workflow uses. DELETE is denied by the guard hook; PUT/PATCH are not used.

## Workflow: comment

Issues have no draft-notes API (unlike MRs): **one note = one notification** to every
participant. Print the text, end the turn, wait for **publish**, then:
```bash
glab issue note <iid> -m "<text>"
```
(In a batch, the `glab api …/notes --method POST --field body=…` form above does the same
without a prompt per note.)

## Workflow: update

Every update is visible to others — print what changes (before → after; for `-d` the whole
new description) and wait for **publish** for
each of: title, description, labels, assignee, close, reopen. `-d` replaces the **whole**
description: to append, fetch the current body (`view --output json | jq -r .description`)
and write the merged text to the scratch file first. Then one of:
```bash
glab issue update <iid> -t "<new title>"
glab issue update <iid> -d "$(cat <scratch-file>)"      # replaces the whole description
glab issue update <iid> -l "add-me" -u "remove-me"      # -l adds, -u removes
glab issue update <iid> -a +<username>                   # +user adds, !user removes; a bare name REPLACES all assignees
glab issue close <iid>
glab issue reopen <iid>
```

## Search

`--search` is an AND over the words, so one broad query misses paraphrases. Run 2–3 short
queries (title words, a path from the body, a label) and union the results by iid.
```bash
# open issues, words in title or description
glab issue list --search "<words>" --in title,description --output json -P 100

# by label, by author, including closed
glab issue list --label improvement --output json -P 100
glab issue list --author @me
glab issue list --search "<words>" -A --output json -P 100       # -A = open + closed

# only ids/urls
glab issue list --search "<words>" -F ids
```
Report matches as `#<iid> <title> [labels] (state)`; say "no match" explicitly when empty.

## View

```bash
glab issue view <iid>                 # title, description, labels, assignees, state
glab issue view <iid> --comments      # plus the discussion
glab issue view <iid> --output json   # fields: iid, title, labels, state, web_url, ...

# structured notes, all pages, no system messages
glab api "projects/:fullpath/issues/<iid>/notes" --paginate \
  | jq -r '.[] | select(.system == false) | "▎ @\(.author.username) (\(.created_at | split("T")[0])): \(.body)"'
```

## Labels

```bash
glab api "projects/:fullpath/labels?per_page=100" | jq -r '.[] | "\(.name)\t\(.description // "")"'
```
Use only names from this list. Creating a label is not this skill's job — report the gap.

## Tips

- `glab issue list` returns 30 per page by default — pass `-P 100`, and `-p 2` if the first
  page is full.
- `--output json` + `jq` for anything that feeds another step; plain text for the user.
- `--paginate` for list endpoints (notes) — GitLab pages at 20. Put the `"projects/…"` path
  right after `glab api` and the flags after it: the allow rule is a prefix match on
  `glab api "projects/`, so `glab api --paginate "projects/…"` prompts every time.
- An MR with `Closes #<iid>` in its description closes the issue on merge
  (`autoclose_referenced_issues` is on for this project).
