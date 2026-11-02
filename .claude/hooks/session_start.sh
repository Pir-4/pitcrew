#!/bin/sh
# SessionStart hook: warns about missing tools and .env values teammates need.
# Plain POSIX shell, no project dependencies (runs before `uv sync` / `make setup`).
# Never prints a token value. Always exits 0.

ENV_FILE="${CLAUDE_PROJECT_DIR:-.}/.env"

# jq: needed by the glab api guard hook and the gitlab skills
check_jq() {
  command -v jq >/dev/null 2>&1 || echo 'WARN: jq not found — the glab api guard hook (PreToolUse) and the gitlab-mr / gitlab-issue skills need it. Run: make install-jq'
}

# glab: binary present, then log in with GITLAB_TOKEN from .env
check_glab() {
  GITLAB_HOST=$(grep -E '^GITLAB_HOST=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)
  GITLAB_TOKEN=$(grep -E '^GITLAB_TOKEN=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)
  if ! command -v glab >/dev/null 2>&1; then
    echo 'WARN: glab not found — the gitlab-mr and gitlab-issue skills need it. Run: make install-glab'
  elif [ -n "$GITLAB_TOKEN" ]; then
    glab auth login --hostname "$GITLAB_HOST" --token "$GITLAB_TOKEN" --git-protocol https || echo 'WARN: glab auth login failed (check token/network/hostname)'
  else
    echo 'WARN: glab auth skipped (GITLAB_TOKEN not found in .env)'
  fi
}

# rg (ripgrep): skills search with it
check_rg() {
  command -v rg >/dev/null 2>&1 || echo 'WARN: rg (ripgrep) not found — skills search with it. Run: make install-ripgrep'
}

# ATLASSIAN_TOKEN in .env: needed by /load-docs (jira-extractor / confluence-extractor)
check_atlassian_token() {
  if ! grep -qE '^ATLASSIAN_TOKEN=.+' "$ENV_FILE" 2>/dev/null; then
    echo 'WARN: ATLASSIAN_TOKEN not found in .env — /load-docs cannot fetch Jira/Confluence. Run: make create-env (or add ATLASSIAN_TOKEN=<token> to .env)'
  fi
}

# jira-extractor / confluence-extractor: needed by /load-docs
check_atlassian_extractors() {
  command -v jira-extractor >/dev/null 2>&1 || echo 'WARN: jira-extractor not found — /load-docs will not work. Run: make install-atlassian-extractors'
}

# codebase-memory-mcp binary: needed by the MCP server from .mcp.json
check_codebase_memory() {
  if [ -x "$HOME/.local/bin/codebase-memory-mcp" ]; then
    echo "codebase-memory-mcp: $("$HOME/.local/bin/codebase-memory-mcp" --version)"
  else
    echo 'WARN: codebase-memory-mcp binary not found — the codebase-memory-mcp server from .mcp.json will not start. Run: make install-codebase-memory-mcp'
  fi
}

# ALLURE_TOKEN in .env: needed by the allure-testops MCP server
check_allure_token() {
  if ! grep -qE '^ALLURE_TOKEN=.+' "$ENV_FILE" 2>/dev/null; then
    echo 'WARN: ALLURE_TOKEN not found in .env — the allure-testops MCP server will not start. Run: make create-env (or add ALLURE_TOKEN=<token> to .env)'
  fi
}

# node: needed by the allure-testops MCP server (npx mcp-remote)
check_node() {
  command -v node >/dev/null 2>&1 || echo 'WARN: node not found — the allure-testops MCP server from .mcp.json will not start. Run: make install-node'
}

check_jq
check_glab
check_rg
check_atlassian_token
check_atlassian_extractors
check_codebase_memory
check_allure_token
check_node

exit 0
