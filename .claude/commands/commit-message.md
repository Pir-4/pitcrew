---
model: haiku
---

# Generate Commit Message (--staged: current only | --branch: full branch | file1 file2: specific files)

Generate a commit message. Mode is selected via argument or auto-detected.

## Mode Detection

Check `$ARGUMENTS`:
- `--staged` → analyze only current staged/unstaged changes (no questions asked)
- `--branch` → analyze full branch vs master (no questions asked)
- Any other non-empty argument → Files Mode (treat all arguments as file paths)
- No argument → run `git diff --cached --stat && git diff --stat` to check for staged or unstaged changes:
  - If any changes exist → ASK user: "Current changes detected. Analyze current changes only, or full branch? [staged/branch]"
  - If no changes → use Branch Mode

## Files Mode Process

1. Parse file paths from `$ARGUMENTS`. Strip `--files` prefix if present. Split by spaces. Strip any leading `@` characters from each path.
2. Get staged changes: `git diff --cached -- <files>`
3. Get unstaged changes: `git diff -- <files>`
4. Get file status: `git status --porcelain -- <files>`
5. For each file listed as untracked (`??`) in step 4: `git diff --no-index /dev/null <file>`
6. If steps 2-5 produced NO diff output → the files have no changes. Output: "No changes detected in specified files." and STOP.
7. Get branch name for Jira ID: `git branch --show-current`
8. If no Jira ID in branch name, check: `git log --oneline -5`
9. If still no Jira ID → ASK user
10. Analyze ONLY the changes from steps 2–5 and generate commit message
11. Invoke the `commit-message-format` skill (Skill tool); follow its rules exactly to build the message.


## Branch Mode Process

1. Get current branch name: `git branch --show-current`
2. Find merge-base with master: `git merge-base HEAD master`
3. Get committed changes on branch: `git diff <merge-base>...HEAD`
4. Get staged changes: `git diff --cached`
5. Get unstaged changes: `git diff`
6. Get untracked files: `git status --porcelain`
7. Get commit history: `git log <merge-base>..HEAD --oneline`
8. Extract Jira ID from branch name or previous commits
9. If no Jira ID found, ASK user for it
10. Analyze ALL changes (committed + staged + unstaged + untracked) and generate commit message
11. Invoke the `commit-message-format` skill (Skill tool); follow its rules exactly to build the message.

## Staged Mode Process

1. Get staged changes: `git diff --cached`
2. Get unstaged changes: `git diff`
3. Get untracked files: `git status --porcelain`
4. Get branch name for Jira ID: `git branch --show-current`
5. If no Jira ID in branch name, check: `git log --oneline -5`
6. If still no Jira ID → ASK user
7. Analyze ONLY current changes and generate commit message
8. Invoke the `commit-message-format` skill (Skill tool); follow its rules exactly to build the message.

## Message Format

The format is owned by the **`commit-message-format` skill** — invoke it (Skill tool) before writing
the message and follow it exactly. It defines the `<JIRA-ID>: <Summary>` title, gitlint constraints,
Jira ID resolution, summary/body rules, and the output discipline.

Hard rules that survive regardless: output ONLY the commit message as plain text — no preamble, no
code blocks, no commentary. The very first character of your output MUST be the Jira ID prefix.
The message ALWAYS has a body of at least one bullet, however small the change (a title alone is
rejected), and NEVER a trailer (`Co-Authored-By`, `Generated with`, …).

## User Context (optional)

$ARGUMENTS
