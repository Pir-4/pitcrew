.PHONY: setup install-uv install-hooks run trigger run-status agent-smoke test coverage lint format fix typecheck lock-check install-colima colima-start colima-stop colima-trust-ca docker-build docker-run docker-up docker-agent-smoke check-brew create-env create-service-env install-ai-tools install-node install-ripgrep install-jq install-glab install-codebase-memory-mcp install-matt-pocock-skills install-atlassian-extractors

# Private PyPI index (auth via ~/.netrc for gitlab.ston.fi).
STONFI_INDEX = https://gitlab.ston.fi/api/v4/projects/809/packages/pypi/simple

# One-time setup of a fresh clone: uv, Python 3.13 + dependencies, git hooks.
setup:
	@$(MAKE) install-uv
	@echo "Syncing dependencies (uv installs Python 3.13 if needed)..."
	@uv sync
	@$(MAKE) install-hooks
	@echo "Done. Next: 'make create-env' and 'make create-service-env', then 'make install-ai-tools' for the agent tooling."

install-uv:
	@if command -v uv >/dev/null 2>&1; then \
		echo "uv: $$(uv --version)"; \
	else \
		echo "Installing uv..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
		echo "uv is installed to ~/.local/bin; restart the shell if it is not on PATH yet."; \
	fi

# pre-commit stage: uv lock, ruff check --fix + ruff format, branch-name check.
# commit-msg stage: gitlint against .gitlint (title must start with GW-<id>:).
install-hooks:
	@uv run pre-commit install
	@uv run pre-commit install-hooks

# Local dev server with reload; Swagger UI at http://127.0.0.1:8000/docs. Logs as console lines;
# `make run LOG_FORMAT=json` shows them as the deploy writes them.
LOG_FORMAT ?= console
run:
	@LOG_FORMAT=$(LOG_FORMAT) uv run uvicorn pitcrew.main:app --reload

# Talk to the local service the way the CI step of qa_automation will. The bearer token is
# PITCREW_TRIGGER_TOKEN from the environment, else from src/service.env.
TEAM ?= Gateway
ENV ?= staging
PITCREW_URL ?= http://127.0.0.1:8000
READ_TOKEN = token="$${PITCREW_TRIGGER_TOKEN:-$$([ -f src/service.env ] && sed -n 's/^PITCREW_TRIGGER_TOKEN=//p' src/service.env)}"; \
	[ -n "$$token" ] || { echo "Error: PITCREW_TRIGGER_TOKEN is not set (make create-service-env)"; exit 1; }

# Send a Run chain trigger; the answer holds the trace id of its Run chain (`make run-status`):
#   make trigger STEP=night_run PIPELINE=478951 LAUNCH=276357 [TEAM=Gateway ENV=staging]
#   make trigger STEP=night_rerun PIPELINE=<Rerun pipeline> LAUNCH=<Rerun launch>
trigger:
	@if [ -z "$(STEP)" ] || [ -z "$(PIPELINE)" ] || [ -z "$(LAUNCH)" ]; then \
		echo "Usage: make trigger STEP=night_run|night_rerun PIPELINE=<pipeline id> LAUNCH=<Allure launch id> [TEAM=$(TEAM) ENV=$(ENV)]"; \
		exit 1; \
	fi
	@$(READ_TOKEN); \
	curl -sS -w '\nHTTP %{http_code}\n' -X POST "$(PITCREW_URL)/triggers" \
		-H "Authorization: Bearer $$token" \
		-H "Content-Type: application/json" \
		-d '{"environment": "$(ENV)", "team": "$(TEAM)", "pipeline_id": $(PIPELINE), "step": "$(STEP)", "allure_launch_id": $(LAUNCH)}'

# Show the status of a Run chain and its Runs, by the trace id `make trigger` printed:
#   make run-status TRACE=<trace id>
run-status:
	@if [ -z "$(TRACE)" ]; then \
		echo "Usage: make run-status TRACE=<trace id answered by make trigger>"; \
		exit 1; \
	fi
	@$(READ_TOKEN); \
	curl -sS -w '\nHTTP %{http_code}\n' "$(PITCREW_URL)/run-chains/$(TRACE)" \
		-H "Authorization: Bearer $$token"

# Ask the Agent about qa_automation in a Working copy and print its answer; needs LITELLM_KEY.
# REF defaults to the Team config's Rerun branch, PROMPT to "describe the repo":
#   make agent-smoke [REF=<branch, tag or commit>] [PROMPT="..."] [TEAM=Gateway]
AGENT_SMOKE = pitcrew agent-smoke --team "$(TEAM)" $(if $(REF),--ref "$(REF)") $(if $(PROMPT),--prompt "$(PROMPT)")
agent-smoke:
	@LOG_FORMAT=$(LOG_FORMAT) uv run $(AGENT_SMOKE)

test:
	@uv run pytest

# Tests with line and branch coverage (config in pyproject.toml); fails under `fail_under`.
coverage:
	@uv run pytest --cov --cov-report=term

lint:
	@uv run ruff check .
	@uv run ruff format --check .

format:
	@uv run ruff format .

fix:
	@uv run ruff check --fix .
	@uv run ruff format .

typecheck:
	@uv run ty check

lock-check:
	@uv lock --check

# Local Docker on macOS: Colima (a lightweight VM with Docker Engine) + the docker CLI.
# Once: make install-colima. Then: make docker-up (starts Colima, builds, runs on :8000).
install-colima:
	@$(MAKE) check-brew
	@for pkg in colima docker docker-buildx; do \
		brew list $$pkg >/dev/null 2>&1 || brew install $$pkg; \
	done
	@mkdir -p ~/.docker/cli-plugins
	@ln -sfn "$$(brew --prefix)/opt/docker-buildx/bin/docker-buildx" ~/.docker/cli-plugins/docker-buildx
	@echo "colima: $$(colima version | head -1)"

colima-start:
	@command -v colima >/dev/null 2>&1 || (echo "Error: colima not found. Run: make install-colima" && exit 1)
	@if colima status >/dev/null 2>&1; then echo "colima: already running"; else colima start; fi
	@$(MAKE) colima-trust-ca

colima-stop:
	@colima stop

# The corporate proxy re-signs TLS with its own root CA. macOS trusts it, the
# Colima VM does not, so image pulls fail with "x509: certificate signed by unknown authority".
# Copies the CA from the System keychain into the VM once; skipped when the keychain has no such CA.
PROXY_CA = Corporate Proxy Root CA
colima-trust-ca:
	@if ! security find-certificate -c "$(PROXY_CA)" /Library/Keychains/System.keychain >/dev/null 2>&1; then \
		echo "colima: no $(PROXY_CA) in the System keychain, skipping"; \
	elif colima ssh -- test -f /usr/local/share/ca-certificates/proxy-root-ca.crt; then \
		echo "colima: $(PROXY_CA) already trusted"; \
	else \
		echo "colima: installing $(PROXY_CA) into the VM..."; \
		security find-certificate -c "$(PROXY_CA)" -p /Library/Keychains/System.keychain \
			| colima ssh -- sudo tee /usr/local/share/ca-certificates/proxy-root-ca.crt >/dev/null; \
		colima ssh -- sudo update-ca-certificates >/dev/null; \
		colima ssh -- sudo systemctl restart docker; \
	fi

# DOCKER_PLATFORM=linux/amd64 builds and runs the architecture the CI build produces (emulated
# on an arm64 Mac); empty: the host's own.
DOCKER_PLATFORM ?=
DOCKER_PLATFORM_FLAG = $(if $(DOCKER_PLATFORM),--platform $(DOCKER_PLATFORM))

docker-build:
	@docker build $(DOCKER_PLATFORM_FLAG) -t pitcrew .

# src/service.env, when present, goes in as environment variables, the way Helm injects them
# at deploy; the root .env never reaches the container. PITCREW_WORK_DIR is a host directory
# mounted into the container (a volume at deploy), so the clone of the test repo outlives the
# container. Not var/workspace of `make run`: git and Claude Code keep absolute paths there.
# PITCREW_WORK_DIR is set after the env file, so the mount is used whatever the file says.
# DOCKER_RUN creates the host directory first. On a Linux host the directory must be writable by uid 1000, the image's user; Colima maps it.
DOCKER_WORK_DIR = var/docker-workspace
DOCKER_RUN = mkdir -p $(DOCKER_WORK_DIR) && docker run --rm $(DOCKER_PLATFORM_FLAG) \
	$$([ -f src/service.env ] && echo --env-file src/service.env) \
	-e PITCREW_WORK_DIR=/app/var/workspace -v "$(CURDIR)/$(DOCKER_WORK_DIR):/app/var/workspace"

# Runs in the foreground on http://127.0.0.1:8000, Ctrl+C stops and removes the container.
docker-run:
	@$(DOCKER_RUN) -p 8000:8000 pitcrew

docker-up:
	@$(MAKE) colima-start
	@$(MAKE) docker-build
	@$(MAKE) docker-run

# `make agent-smoke` inside the image, in a container of its own beside `make docker-up`'s:
# the image's git, user and bundled Claude Code, the Working copy in DOCKER_WORK_DIR.
#   make docker-agent-smoke [REF=...] [PROMPT="..."] [TEAM=Gateway] [DOCKER_PLATFORM=linux/amd64]
docker-agent-smoke:
	@$(MAKE) colima-start
	@$(MAKE) docker-build
	@$(DOCKER_RUN) -e LOG_FORMAT=$(LOG_FORMAT) pitcrew $(AGENT_SMOKE)

# Homebrew is how every CLI below gets installed (glab, ripgrep, jq, node); fail once, early.
check-brew:
	@command -v brew >/dev/null 2>&1 || (echo "Error: Homebrew not found. Install it first: https://brew.sh" && exit 1)

# Node.js: needed by the allure-testops MCP server (npx mcp-remote).
install-node:
	@$(MAKE) check-brew
	@if command -v node >/dev/null 2>&1; then \
		echo "node: $$(node -v)"; \
	else \
		echo "Installing Node.js via Homebrew..."; \
		brew install node; \
	fi

# Create .env with the values the agent tooling needs (see .env.example).
create-env:
	@if [ -f ".env" ]; then \
		echo ".env file already exists."; \
		echo "Do you want to recreate the .env file? (y/n): "; \
		read recreate; \
		if [ "$$recreate" != "y" ]; then \
			echo "Exiting without creating .env file."; \
			exit 0; \
		fi; \
	fi; \
	echo "Creating new .env file..."; \
	echo "## ATLASSIAN ##" > .env; \
	echo "ATLASSIAN_URL=https://stonfi.atlassian.net/" >> .env; \
	echo "Enter value for ATLASSIAN_EMAIL (your corporate email): "; \
	read atlassian_email; \
	echo "ATLASSIAN_EMAIL=$$atlassian_email" >> .env; \
	echo "Enter value for ATLASSIAN_TOKEN (https://id.atlassian.com/manage-profile/security/api-tokens): "; \
	read atlassian_token; \
	echo "ATLASSIAN_TOKEN=$$atlassian_token" >> .env; \
	echo "" >> .env; \
	echo "## GITLAB ##" >> .env; \
	echo "# Token required scopes: api (read MRs + post draft notes/comments)" >> .env; \
	echo "# Generate at: https://gitlab.ston.fi/-/user_settings/personal_access_tokens" >> .env; \
	echo "GITLAB_HOST=gitlab.ston.fi" >> .env; \
	echo "Enter value for GITLAB_TOKEN (scope: api - for reading MRs and posting draft comments): "; \
	read gitlab_token; \
	echo "GITLAB_TOKEN=$$gitlab_token" >> .env; \
	echo "" >> .env; \
	echo "## ALLURE TESTOPS ##" >> .env; \
	echo "# Used by the allure-testops MCP server declared in .mcp.json (Claude Code)" >> .env; \
	echo "# Generate at: https://testops.ston.fi/ -> profile -> API tokens" >> .env; \
	echo "Enter value for ALLURE_TOKEN (Allure TestOps API token, optional): "; \
	read allure_token; \
	echo "ALLURE_TOKEN=$$allure_token" >> .env; \
	echo "" >> .env; \
	echo ".env file has been created."

# Create src/service.env, the service's own config, from src/service.env.example: comments are
# copied, each NAME=default line is asked for (Enter keeps the default). The template is read on
# fd 3 so that `read` takes the answers from the terminal.
create-service-env:
	@if [ -f src/service.env ]; then \
		echo "src/service.env file already exists."; \
		echo "Do you want to recreate the src/service.env file? (y/n): "; \
		read recreate; \
		if [ "$$recreate" != "y" ]; then \
			echo "Exiting without creating src/service.env file."; \
			exit 0; \
		fi; \
	fi; \
	echo "Creating new src/service.env file..."; \
	: > src/service.env; \
	while IFS= read -r line <&3 || [ -n "$$line" ]; do \
		case "$$line" in \
			[A-Z]*=*) \
				name="$${line%%=*}"; default="$${line#*=}"; \
				echo "Enter value for $$name [$$default]: "; \
				IFS= read -r value; \
				printf '%s=%s\n' "$$name" "$${value:-$$default}" >> src/service.env ;; \
			*) printf '%s\n' "$$line" >> src/service.env ;; \
		esac; \
	done 3< src/service.env.example; \
	echo "src/service.env file has been created."

# Everything the Claude Code tooling in .claude/ and .mcp.json needs. Idempotent.
install-ai-tools:
	@$(MAKE) install-node
	@$(MAKE) install-ripgrep
	@$(MAKE) install-jq
	@$(MAKE) install-glab
	@$(MAKE) install-codebase-memory-mcp
	@$(MAKE) install-matt-pocock-skills
	@$(MAKE) install-atlassian-extractors

# jira-extractor / confluence-extractor for the /load-docs command. Installed as a global
# uv tool (no pyproject.toml needed yet); they read ATLASSIAN_* from .env in the cwd.
install-atlassian-extractors:
	@command -v uv >/dev/null 2>&1 || (echo "Error: uv not found. Install it first: https://docs.astral.sh/uv/getting-started/installation/" && exit 1)
	@test -f ~/.netrc || (echo "Error: ~/.netrc not found. Create it with: echo \"machine gitlab.ston.fi login {gitlab_username} password {gitlab_token}\" > ~/.netrc && chmod 600 ~/.netrc" && exit 1)
	@if command -v jira-extractor >/dev/null 2>&1; then \
		echo "atlassian-extractors: already installed"; \
	else \
		echo "Installing atlassian-extractors (uv tool)..."; \
		uv tool install atlassian-extractors --index $(STONFI_INDEX); \
	fi

# Matt Pocock's engineering skills (grill-me, to-spec, tdd, triage, ...) as a Claude Code plugin.
# Enabled for the team in .claude/settings.json (enabledPlugins); the plugin updates itself.
# Repo-level config (docs/agents/, GLOSSARY.md, docs/adr/) is committed, so no per-clone setup.
install-matt-pocock-skills:
	@if claude plugin list 2>/dev/null | grep -q "mattpocock-skills@claude-plugins-official"; then \
		echo "mattpocock-skills: already installed"; \
	else \
		echo "Installing mattpocock-skills Claude Code plugin..."; \
		claude plugin install mattpocock-skills@claude-plugins-official; \
	fi

install-glab:
	@$(MAKE) check-brew
	@if ! command -v glab >/dev/null 2>&1; then \
		echo "Installing glab via Homebrew..."; \
		brew install glab; \
	fi; \
	echo "glab: $$(glab --version | head -1)"

install-ripgrep:
	@$(MAKE) check-brew
	@if ! command -v rg >/dev/null 2>&1; then \
		echo "Installing ripgrep via Homebrew..."; \
		brew install ripgrep; \
	fi; \
	echo "ripgrep: $$(rg --version | head -1)"

# jq: parses glab JSON in the gitlab-mr / gitlab-issue skills and in the PreToolUse guard
# hook for `glab api` (.claude/settings.json). Without it the hook falls back to raw matching.
install-jq:
	@$(MAKE) check-brew
	@if ! command -v jq >/dev/null 2>&1; then \
		echo "Installing jq via Homebrew..."; \
		brew install jq; \
	fi; \
	echo "jq: $$(jq --version)"

# Installed to ~/.local/bin — the same path .mcp.json starts it from, so check that path, not PATH.
install-codebase-memory-mcp:
	@if [ -x "$$HOME/.local/bin/codebase-memory-mcp" ]; then \
		echo "codebase-memory-mcp: already installed ($$("$$HOME/.local/bin/codebase-memory-mcp" --version))"; \
	else \
		echo "Installing codebase-memory-mcp..."; \
		curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash; \
	fi
	@echo "Claude Code starts the server from .mcp.json; it is already enabled for the team in .claude/settings.json (enabledMcpjsonServers)."
