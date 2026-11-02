#!/bin/sh
# PreToolUse hook (matcher Bash). Project policy that must hold in every permission mode,
# auto mode included (a hook "deny" is enforced; settings.json "ask" rules are not in auto mode):
#   1. git:   deny force-push, push to master/main, and --no-verify on push/commit.
#   2. .env:  deny shell commands that read .env or service.env (or .env.<x>, except
#             the .env.example / service.env.example templates).
#   3. glab api: deny DELETE and MR approve/unapprove/merge endpoints; ask on any other write
#              (non-GET method, or -f/-F/--field/--raw-field/--input, which make glab POST).
# Plain POSIX shell, needs jq. Always exits 0.

CMD=$(jq -r '.tool_input.command // ""' 2>/dev/null || cat)

decide() { # $1 = deny|ask, $2 = reason
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"%s","permissionDecisionReason":"%s (.claude/hooks/bash_guard.sh)"}}\n' "$1" "$2"
  exit 0
}

has() { printf '%s' "$CMD" | grep -qE -- "$1"; }
has_i() { printf '%s' "$CMD" | grep -qiE -- "$1"; }

W='(^|[[:space:];&|(])'   # start of a command word

# 1. git
if has "${W}git[[:space:]]+push([[:space:]]|$)"; then
  has '[[:space:]](--force|--force-with-lease|--force-if-includes|-f)([[:space:]=]|$)' && decide deny "git push --force is blocked by project policy"
  has '[[:space:]]\+[^[:space:]]' && decide deny "git push with a +refspec (force) is blocked by project policy"
  has '[[:space:]:](master|main)([[:space:]]|$)' && decide deny "git push to master/main is blocked by project policy - push a branch and open an MR"
  has '[[:space:]]--no-verify([[:space:]]|$)' && decide deny "git push --no-verify is blocked by project policy"
fi
if has "${W}git[[:space:]]+commit([[:space:]]|$)"; then
  has '[[:space:]]--no-verify([[:space:]]|$)' && decide deny "git commit --no-verify is blocked: it skips gitlint and the branch-name check"
fi

# 2. .env / service.env reads (the .env.example / service.env.example templates are fine)
STRIPPED=$(printf '%s' "$CMD" | sed 's/\.env\.example//g')
if printf '%s' "$STRIPPED" | grep -qE '(^|[^A-Za-z0-9_])(service)?\.env([^A-Za-z0-9_]|$)'; then
  if printf '%s' "$STRIPPED" | grep -qE "${W}(cat|less|more|head|tail|bat|rg|grep|egrep|fgrep|sed|awk|cut|sort|uniq|tr|xxd|od|strings|base64|jq|cp|mv|tee|diff|source|\.|python3?|node|perl|ruby|env)([[:space:]]|$)"; then
    decide deny "reading .env or service.env from the shell is blocked: secrets must not enter the transcript"
  fi
fi

# 3. glab api
if has "${W}glab[[:space:]]+api([[:space:]]|$)"; then
  M='(--method[[:space:]=]+|-X[[:space:]=]*)["'"'"'\\]*'
  has_i "${M}delete([^a-z]|$)" && decide deny "glab api DELETE is blocked by project policy"
  has '/merge_requests/[^/[:space:]]+/(approve|unapprove|merge)([^a-z_]|$)' && decide deny "approving or merging an MR through glab api is blocked: a human merges"
  has_i "${M}(post|put|patch)([^a-z]|$)" && decide ask "glab api write (non-GET) changes GitLab objects - confirm"
  has '[[:space:]](-f|-F|--field|--raw-field|--input)([[:space:]=]|$)' && decide ask "glab api with fields/input sends a POST - confirm"
fi

exit 0
