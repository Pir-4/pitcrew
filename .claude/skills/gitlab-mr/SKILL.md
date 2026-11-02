---
name: gitlab-mr
description: Access GitLab Merge Requests — list, view diffs, read review comments, post notes. Use when the user asks to review an MR, check MR comments, show MR diff, look at review feedback, or work with GitLab merge requests.
allowed-tools: Bash(glab mr list*), Bash(glab mr view*), Bash(glab mr diff*), Bash(glab mr checkout*), Bash(glab mr note*), Bash(glab pipeline list*), Bash(glab ci trace*), Bash(glab api "projects/*), Bash(jq *), Bash(git diff*), Bash(rg *)
model: haiku
---

# GitLab Merge Requests with glab CLI

## Repository

This skill operates exclusively on:
- **Host:** `gitlab.ston.fi`
- **Project:** `valentin.agapitov/pitcrew` (id 1269)
- **Encoded path:** `valentin.agapitov%2Fpitcrew`

Credentials are persisted via `glab auth login` — no env var needed before commands.
`.env` is loaded automatically at session start via `SessionStart` hook.


## Rules — never violate

- **Never** run `glab mr merge`, `glab mr delete`, or `glab mr approve` *(hard-blocked in project settings)*
- **Never** use `glab api --method DELETE`, `--method PUT`, or `--method PATCH` via the REST API
- **Always** warn the user before running `glab mr checkout` — it modifies the working tree and changes the current branch
- **POST is allowed** only for draft notes (`draft_notes`, `draft_notes/bulk_publish`) — never for merge or approve endpoints

## Comment workflow — always follow this

When asked to reply to or write review comments:
1. **Draft first** — compose the comment text and show it to the user for review
2. **Wait for explicit approval** — do not post anything until the user confirms
3. **Post as draft note** — use the draft notes API, never `glab mr note` directly
4. **Publish together** — collect all drafts, publish in bulk only when the user says "publish" or "submit review"

This avoids spamming colleagues with individual notifications — all comments land as one review submission.

After posting each approved draft, always remind the user:
> "Draft posted. X draft(s) pending — say **'publish drafts'** when ready to submit the review."

When showing review comments or discussions:

**Priority order:**
1. **CODE REVIEW THREADS** (inline on specific lines)
   - Format: `[✅/❌] file:line` with all notes in thread grouped together
   - Show author, date, comment text in order

2. **GENERAL FEEDBACK** (comments not tied to code)
   - Format: `[@author] date` with comment
   - Exclude system messages (commits, description changes)

3. **PENDING DRAFTS** (not yet published)
   - Format: `▎ Draft by @author: text`

**Rules:**
- Skip system comments (contain "commit", "changed", "added", "marked")
- Group threaded replies under one file:line location
- Show timestamps to understand conversation flow
- If multiple threads on same file, order by line number
- Always show status (✅ resolved / ❌ unresolved)
- Truncate long comments but keep them readable

---

## Quick start

```bash
# List open MRs in current project
glab mr list

# View MR with full description and comments
glab mr view 123 --comments

# Show what files changed in MR
glab mr view 123 --output json | jq '.changes[].new_path'
```

---

## Commands

### List MRs

```bash
# All open MRs in current project
glab mr list

# MRs assigned to me
glab mr list --assignee @me

# MRs awaiting my review
glab mr list --reviewer @me

# My own MRs
glab mr list --author @me

# Closed/merged MRs
glab mr list --state merged
glab mr list --state closed

# JSON output for parsing
glab mr list --output json
```

### View MR details

```bash
# Basic info (title, description, status, assignee, reviewer)
glab mr view 123

# Full view including all review comments and discussions
glab mr view 123 --comments

# JSON for structured access
glab mr view 123 --output json
```

### View diff / changed files

```bash
# List changed files in MR (via JSON)
glab mr view 123 --output json | jq -r '.changes[].new_path'

# Show diff of a specific file using git after checkout
glab mr checkout 123
git diff origin/<target-branch>..HEAD -- path/to/file.py
```

### Read discussions and review comments

**Best approach — all real feedback with reply chains:**

```bash
# Show only real feedback comments (filter out system + version changes)
glab api "projects/:fullpath/merge_requests/123/discussions" --paginate | jq -r \
  '[.[] | select(.notes | any(.system == false))] | sort_by(.notes[0].position.new_line // 999) | .[] |
   "[\(if .resolved then "✅" else "❌" end)] \(.notes[0].position.new_path // "general"):\(.notes[0].position.new_line // "N/A")\n\(.notes | map(select(.system == false and (.body | contains("changed this line") | not)) | "  ▎ @\(.author.username) (\(.created_at | split("T")[0])): \(.body | gsub("<[^>]*>"; "") | gsub("\n"; " ") | if length > 110 then .[0:110] + "..." else . end)") | select(length > 0) | join("\n"))\n" | select(length > 0)'

# Draft notes (not yet published)
glab api "projects/:fullpath/merge_requests/123/draft_notes" --paginate | jq -r '.[] | "▎ Draft: @\(.author.username)\n  \(.note)"'
```

**Output format (real feedback only):**

```
[❌] product/emails/provider.py:48
  ▎ @anna.sokolova (2026-06-26): looks complicated imho, can we reuse our exist polling?
  ▎ @valentin.agapitov (2026-06-26): done
  ▎ @valentin.agapitov (2026-06-29): Deleted. No longer relevant.

[✅] product/emails/email_manager.py:256
  ▎ @ivan.petrov (2026-06-25): Lets use new approach, like `get_registration_emails`
  ▎ @valentin.agapitov (2026-06-25): done

[❌] general:N/A
  ▎ @anna.sokolova (2026-06-26): lets merge master to your branch. Some tests for Wallet...
```

**Filters applied:**
- `system == false` — skip system messages (commits, changed description, etc)
- `contains("changed this line")` — skip version change markers
- `select(length > 0)` — skip empty threads

### Post comments (draft workflow)

```bash
# Create a draft note (preferred — does not notify colleagues)
glab api "projects/:fullpath/merge_requests/123/draft_notes" \
  --method POST --field note="your comment text"

# List all current draft notes
glab api "projects/:fullpath/merge_requests/123/draft_notes" --paginate

# Publish all drafts at once (triggers single notification to colleagues)
glab api "projects/:fullpath/merge_requests/123/draft_notes/bulk_publish" \
  --method POST

# Direct comment without draft — only with explicit user instruction
glab mr note 123 --message "text"
```

### MR status & CI

```bash
# Check pipeline status
glab mr view 123 --output json | jq '.head_pipeline.status'

# List checks / CI jobs
glab pipeline list --mr 123
```

### CI job logs (for failure analysis)

```bash
# Pipeline id for the MR, then jobs in that pipeline with status
PIPELINE_ID=$(glab mr view 123 --output json | jq '.head_pipeline.id')
glab api "projects/:fullpath/pipelines/$PIPELINE_ID/jobs" | jq -r '.[] | "\(.id) \(.status) \(.name)"'

# Full log of one job — works for finished jobs too (prints and exits, no need to wait)
glab ci trace <job_id>

# Same, but as raw text saved to a file for grep/analysis on long logs
glab api "projects/:fullpath/jobs/<job_id>/trace" > <scratchpad>/job_<job_id>.log
grep -n -iE 'error|fail|traceback|assert' <scratchpad>/job_<job_id>.log
```

Use this when the user asks to analyze a failed CI run, explain why a job failed, or debug a pipeline linked to an MR.

---

## Workflow: Full MR review

```bash
# 1. List MRs waiting for my review
glab mr list --reviewer @me

# 2. View MR with all comments
glab mr view 123 --comments

# 3. Fetch structured discussions for analysis
glab api "projects/:fullpath/merge_requests/123/discussions" --paginate | jq .

# 4. Compose comment → show to user → wait for approval → post as draft
glab api "projects/:fullpath/merge_requests/123/draft_notes" \
  --method POST --field note="comment text"

# 5. Review pending drafts before publishing
glab api "projects/:fullpath/merge_requests/123/draft_notes" --paginate

# 6. Publish all drafts — only when user explicitly says to submit
glab api "projects/:fullpath/merge_requests/123/draft_notes/bulk_publish" \
  --method POST
```

---

## Working with project path

`:fullpath` in `glab api` calls is replaced automatically when running from inside the repo (current working directory).

If needed explicitly:
```bash
glab api "projects/valentin.agapitov%2Fpitcrew/merge_requests/123/discussions" --paginate
```

---

## Tips

- Always add `--paginate` (after the quoted `"projects/…"` path, so the allow rule matches) for list endpoints (discussions, draft_notes) — GitLab returns only 20 items per page by default; without it long MRs silently lose comments
- Auth is persisted via `glab auth login` — no need to load env vars before each command
- `glab mr view <id> --comments` gives the most complete picture for code review
- `glab api` gives raw REST API access when `glab mr` commands don't cover a specific endpoint
- `--output json` + `jq` is the best way to extract specific fields for analysis
