---
version: 1.2
last_updated: 2026-10-08
---

# Load Task Documentation

Load full context for a Jira task: issues, Confluence documentation, and generate `_CONTEXT.md`.

## Tools Required

- **Bash**: run extractors (`jira-extractor`, `confluence-extractor` — installed as a `uv tool`,
  see `make install-atlassian-extractors`; they read `ATLASSIAN_*` from `.env` themselves), git commands
- **AskUserQuestion**: interactive prompts for user choices
- **Read/Write**: manage context files
- **Glob**: check existing files

Output goes to `docs/Product/` (git-ignored, local task context).

## Arguments

Parse `$ARGUMENTS` for inputs and flags:

**Inputs (multiple allowed, space-separated):**
- `<JIRA_ID>` — issue key (e.g., `GW-2`)
- `<JIRA_URL>` — full Jira URL (extracts key)
- `<CONFLUENCE_URL>` — Confluence page URL
- *(none)* — auto-detect from branch name

**Flags:**
- `--refresh` — skip existing context check, force re-download
- `--no-confluence` — skip Confluence pages from Jira descriptions
- `--no-parent` — don't offer to fetch parent epic
- `--no-children` — don't offer to fetch child issues

Examples:
```
/load-docs                           # Auto-detect from branch
/load-docs GW-2                 # Single Jira issue
/load-docs GW-2 GW-9       # Multiple Jira issues
/load-docs --refresh                 # Force refresh current branch issue

# Confluence pages:
/load-docs https://...wiki/.../123
/load-docs https://...wiki/.../123 https://...wiki/.../456

# Mixed mode:
/load-docs GW-2 https://...wiki/.../123
```

## Process

### 1. Parse and Classify Inputs

Split `$ARGUMENTS` by spaces and classify each token:

| Token Pattern | Classification |
|---------------|----------------|
| Starts with `--` | Flag |
| Contains `atlassian.net/wiki` | Confluence URL |
| Contains `atlassian.net/browse/` | Jira URL (extract key after `/browse/`) |
| Matches `[A-Z]+-\d+` | Jira key |

**If no inputs found:**
1. Extract from branch: `git branch --show-current`, match pattern `GW-\d+`
2. If still empty, ask user with free-text input:
   - Question: "Enter Jira key(s) or Confluence URL(s):"
   - Description: "Examples: GW-2, https://...atlassian.net/wiki/... (space-separated for multiple)"
   - Parse the response using the same classification rules above

**Determine primary mode:**
- Jira keys present → Jira mode (first key is primary for _CONTEXT.md)
- Only Confluence URLs → Confluence-only mode

### 2. Check Existing Context

**Skip this step if `--refresh` flag is present.**

Check if context already exists using Glob for `docs/Product/jira/<JIRA_ID>/_CONTEXT.md`.

**If _CONTEXT.md exists:**

Read the file, extract metadata, and ask user: "Context for <JIRA_ID> already exists. What do you want to do?"

Show preview with: fetched timestamp, issues list, Confluence pages, file counts.

Options:
- **Use existing (Recommended):** Show summary. **Stop here.**
- **Refresh:** Continue to Step 3.
- **Add resources:** Skip to Step 4.

**If _CONTEXT.md does not exist:** Continue to Step 3.

### 3. Download Content

#### 3A. Confluence-Only Mode

If only Confluence URLs were provided (no Jira keys):

For each URL, ask user: "Download '<page_title>'?" with options:
- **This page only (Recommended)**
- **Include children** — download page and all child pages
- **Skip**

Download using confluence-extractor (see CLI Commands Reference below).

Show downloaded files summary. Skip to Step 4 or finish. No _CONTEXT.md for Confluence-only mode.

---

#### 3B. Jira Mode — Fetch Main Issue

Fetch the main issue **always with `--include-comments`** (see CLI Commands
Reference). Comments are not optional for the main issue: descriptions
routinely omit the event payloads, error examples and follow-up bug links that
exist only in the discussion.

**Parse JSON output to discover:**
- `parent_key` — parent epic if exists
- `confluence_links` — documentation URLs (also harvested from comment bodies)
- `comments_count` — comments saved into the issue markdown
- Issue type — "Epic" indicates children exist

**Build available options dynamically:**
- **Parent epic** — only if `parent_key` exists
- **Child issues** — only if issue type is "Epic" or has subtasks
- **Confluence pages** — one option per URL in `confluence_links`
- **Comments for parent/child issues** — only if parent or children are
  available. Do **not** pre-select: relatives' discussions are usually noise.
  This choice never affects the main issue, whose comments are always fetched.

**If no options available** (no parent, no children, no confluence): skip this step, proceed directly to Step 3C.

**If options available:** Ask user (multiSelect): "What do you want to include?"
Pre-select: parent (if Story), all Confluence pages.

#### 3C. Download Selected Jira Resources

Download based on user selection using CLI commands (see reference below).

**Ordering rule — the main issue must keep its comments.** `--include-parent`
and `--include-children` re-download the main issue in the same call and
overwrite its markdown file, and `--include-comments` is all-or-nothing per
call. So:

- **Comments for relatives selected** → a single call carrying the relative
  flags *and* `--include-comments`. Everything gets comments, nothing to fix up.
- **Comments for relatives NOT selected** → run the relative flags without
  `--include-comments`, then **finish** by re-fetching the main issue alone:

  ```
  jira-extractor <KEY> --include-comments --output-format json -o <dir>
  ```

  `<dir>` is the directory holding the main issue's file per the previous call's
  `files` array — `--include-children` nests output under `<KEY>/`, without it
  output is flat in `docs/Product/jira/`. Never skip this call and never run it
  before the relative download, or the main issue ends up without comments.

Show download progress with checkmarks for each completed item.

**If `errors` in JSON output:** Show warning with failed issues, continue with successful ones.

### 4. Ask for Additional Resources

Ask user: "Add more resources?" with options:
- **Done** — generate context with current files
- **Add Jira issue** — enter key or URL
- **Add Confluence page** — enter URL

Download each added resource using CLI commands (see reference below).

Repeat until user selects "Done".

### 5. Generate _CONTEXT.md (Jira Mode Only)

Create file `docs/Product/jira/<JIRA_ID>/_CONTEXT.md` using data from JSON outputs:

```markdown
---
jira_id: <JIRA_ID>
fetched_at: <ISO timestamp>
---

# Context: <JIRA_ID> - <Summary>

## Jira Issue

**Key:** <KEY>
**Type:** <type> | **Status:** <status> | **Priority:** <priority>
**URL:** https://stonfi.atlassian.net/browse/<KEY>

### Description

> <description from downloaded markdown, quoted>

### Comments

<comments_count> comment(s) in the issue markdown under `## Comments`. Read them
for event payloads, error examples and follow-up bug links — often the only
place these appear. Omit this section when `comments_count` is absent.

## Documentation

| Document | Path | Source |
|----------|------|--------|
| <title> | `docs/Product/confluence/<filename>.md` | Jira description |
| <title> | `docs/Product/confluence/<filename>.md` | User provided |

## Related Issues

### Parent Issue
- <PARENT_KEY> (<type>) - <summary>
  `docs/Product/jira/<PARENT_KEY>/<filename>.md`

### Child Issues
- <KEY> (<type>) - <summary>
  `docs/Product/jira/<JIRA_ID>/<filename>.md`

### Linked Issues
Dependencies and related issues (clones/duplicates filtered).
- <relationship>: <KEY> - <summary>

### User-Provided Issues
- <KEY> - <summary>
  `docs/Product/jira/<KEY>/<filename>.md`

## Suggested Reading Order

1. This context file
2. Main Jira issue: `docs/Product/jira/<JIRA_ID>/<filename>.md` — including its `## Comments` section
3. Parent epic (if exists): `docs/Product/jira/<PARENT_KEY>/<filename>.md`
4. Confluence documentation
5. Child/linked issues as needed

---
*Generated by /load-docs*
*Timestamp: <ISO timestamp>*
```

## Output

Show final summary:
```
Context loaded for <JIRA_ID>

Jira: X issues
  - GW-2 (Story) - main issue
  - GW-100 (Epic) - parent

Confluence: Y pages
  - <page title>.md

Read: docs/Product/jira/<JIRA_ID>/_CONTEXT.md
```

## CLI Commands Reference

| Action | Command |
|--------|---------|
| Jira: main issue (always) | `jira-extractor <KEY> --include-comments --output-format json -o docs/Product/jira/` |
| Jira: with children | Add `--include-children` flag |
| Jira: with parent | Add `--include-parent` flag |
| Jira: full context | Add `--include-children --include-parent` flags |
| Jira: comments for relatives too | Keep `--include-comments` on the call carrying the relative flags |
| Jira: restore main issue comments | `jira-extractor <KEY> --include-comments --output-format json -o <dir holding the main issue file>` |
| Confluence: single page | `confluence-extractor "<url>" -o docs/Product/confluence/` |
| Confluence: with children | Add `--include-children` flag |

## Error Handling

- **Extractor not found:** tell the user to run `make install-atlassian-extractors` and stop
- **Missing `ATLASSIAN_*` credentials (extractor error):** tell the user to run `make create-env`, never read `.env` yourself
- **Jira errors in JSON `errors[]`:** Show warning, continue with successful issues
- **Confluence download fails:** Show warning, continue
- **No Confluence URLs found:** Note in summary, skip Confluence step
- **Permission denied:** Show error with issue key, suggest checking access

## User Arguments

$ARGUMENTS
