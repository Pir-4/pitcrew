---
name: commit-message-format
description: The commit message contract for this repo — `<JIRA-ID>: <Summary>` title, a mandatory bullet body, imperative mood, gitlint-safe. ALWAYS load this before writing any commit message text in this repository — a `git commit`, an amend, a squash message, a message to paste, or a flow that commits on the user's behalf.
---

# Commit Message Format

The single source of the commit message format for this repo. Every commit message written here — a
`git commit`, an amend, a squash, or a message generated for the user to paste — follows these rules.

This skill owns **the message**, not the diff collection. Which changes to analyse (staged / branch /
specific files) is the caller's job; this skill turns an already-known set of changes into a message.

## Commit Message Format (REQUIRED)

Must pass gitlint validation (see `.gitlint`).

### First Line (Title)
```
<JIRA-ID>: <Summary>
```

**Rules:**
- Max 120 characters
- Must match regex: `^(GW)-\d+:` or `^Merge branch`
- No trailing punctuation (ignored by config but avoid anyway)

Example:
```
GW-8: Add test coverage audit documentation
```

### Jira ID (REQUIRED)
- Extract from branch name pattern: `{JIRA-ID}_{summary}` or `{lastname}/{JIRA-ID}_{summary}`
- Example: `GW-2_init_ai` → `GW-2`
- Valid prefix: `GW` (the list lives in `.gitlint` and `.pre-commit-config.yaml`; extend all three together)
- If not found in branch name, check previous commit messages
- If still not found, **ASK the user** for the Jira ticket ID

### Summary (REQUIRED)
- Imperative mood ("Add feature" not "Added feature")
- No trailing punctuation
- Concise description of changes
- Keep total first line under 120 characters

### Body (REQUIRED — a title alone is never a complete message)
- Blank line after first line
- Bullet points explaining what changed. **At least one bullet, always**, even for a one-line
  or one-file change: the bullet says what changed and where, in full words, and why when that
  is not obvious. A title without a body is the most common defect in this repo's history.
  For a trivial change the bullet is the title's summary without the Jira ID, expanded with the
  file or area — e.g. title `GW-123: Fix the retry delay in the Kafka listener`, bullet
  `- BaseKafkaListener.wait_for_message retried every 0.1 s instead of 1 s; the default was overwritten by the subscribe() kwargs`
- **Order bullets by importance — most significant change first, smallest last.** The reader must get
  the essence of the commit from the first bullet. Ranking, high to low:
  1. New behaviour, new feature, new test coverage
  2. Behaviour changes and fixes to existing code
  3. Refactoring and restructuring with no behaviour change
  4. Docs, config, dependency bumps, formatting, renames, cleanup

  If a bullet spans two tiers, use the higher one. If two bullets share a tier, keep them in the
  order the changes were made.
- Why the change was made (if not obvious)
- No line length limit (B1 ignored)

### Trailers (NONE)
- No `Co-Authored-By`, no `Generated with …`, no `Signed-off-by`, no `Refs:` lines — nothing after
  the last bullet. This repo credits commits to the human author only; the project rule
  overrides any default attribution the assistant would otherwise append. Add a trailer only
  when the user explicitly asks for that trailer.

## Output

Output ONLY the commit message as plain text. No code blocks, no markdown formatting, no explanations, no analysis, no commentary before or after the message.
Do not describe the changes in prose. Do not mention where the Jira ID was extracted from. Do not add any preamble or introduction.
The very first character of your output MUST be the Jira ID prefix (GW).

**CORRECT** (message only, nothing else):

GW-8: Add test coverage audit documentation

- Add coverage legends and risk definitions
- Add feature sections with audit status
- Add cross-feature coverage summary

**WRONG** (has extra text before or around the message — NEVER do this):

The changes add documentation for test coverage. Jira ID from branch: `GW-8`.

GW-8: Add test coverage audit documentation

- Add coverage legends and risk definitions

**WRONG** (has preamble — NEVER do this):

I have enough context. Here's the commit message:

GW-8: Add test coverage audit documentation

- Add coverage legends and risk definitions

**WRONG** (title only — NEVER do this, even for a small fix):

GW-8: Small fix

**CORRECT** for the same small fix:

GW-8: Fix the audit table header in the coverage doc

- docs/test-coverage-audit.md: the legend column was labelled "Risk" twice; the second one is "Status"

**WRONG** (trailer — NEVER do this):

GW-8: Add test coverage audit documentation

- Add coverage legends and risk definitions

Co-Authored-By: Claude <noreply@anthropic.com>

## When the message goes straight into `git commit`

The output rule above governs the *message text*. When it is passed to `git commit -m` or
`-F <file>` rather than printed for the user, the format is unchanged: title `<JIRA-ID>: <Summary>`
in imperative mood, at least one body bullet, no trailers, no commentary inside the message.
