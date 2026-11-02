# Deploy — open questions

What to agree with DevOps before Pitcrew can be deployed and iterated on without external blockers.
Check items off and move decisions into `roadmap.md` as they land.

## Outcome (2026-10-13)

Talked to DevOps and to the CTO. Decision:

- **Deploy is deferred to the rollout phase.** The MVP is built and run locally: the service runs from a
  laptop with personal tokens and is exercised during my on-call. After the demo: security approval,
  stage deploy, CI integration in `qa_automation`.
- **Security** is the main delay: an approval is required before anything runs on stage. It happens at
  rollout, not now.
- **DevOps: not a problem.** They build a Helm chart that holds the whole service configuration: secrets
  path, network, storage. An injector reads secrets from Vault and puts them into env vars.

DevOps answers, in short: a build CI template exists; the chart lives on the DevOps side, we merge
ourselves, auto-deploy on merge to the main branch; a secrets engine for stage is ready; network rules
are part of the chart; no DNS needed, `kubectl port-forward` for local access; MySQL on request; files
preferably in S3 with a deletion policy, volumes are harder; JSON logs on stdout are picked up
automatically.

Rollout checklist:

- [ ] Security approval.
- [ ] DevOps task: Helm chart (secrets, network, S3, DB).
- [ ] Security scans in CI.
- [ ] Open: worktrees and Claude sessions (`CLAUDE_CONFIG_DIR`) need a filesystem while DevOps prefer S3.
      Option: working directory on ephemeral disk (clone and reports are a cache), sessions synced to S3.
      Decide when the chart is designed.

## Known

- Stage is Kubernetes: ArgoCD + Helm, one values repo per stage. Charts come from the internal chart
  registry, lint via the shared `helm-lint` CI template.
- Images: GitLab registry `gitlab.ston.fi:5050/<group>/<project>`, tag = commit sha.
- Secrets: Vault (`vaultPath` in values). I have access to the stage namespace.
- Network: a network policy per service, closed by default. GitLab runner is in-cluster (`gitlab-runner` namespace).
- Nightly trigger: a CI step in `qa_automation` calls Pitcrew. No public ingress needed, internal Service + an ingress rule from the runner.
- Report: Slack, same channel as `qa_automation`, webhook taken from that repo.
- Tests already reach Allure TestOps; GitLab API most likely.
- Jira integration is deferred to a later step, may not be approved. Not in this round.
- QA owns `qa_automation`: the bot account, the webhook and the CI step are agreed with them.

## DevOps

**Repo location**
- [ ] The repo is in the personal namespace (`valentin.agapitov/pitcrew`). Fine for the MVP, or does build and deploy setup require moving it to a group? If so, which one.
- [ ] If fine for now: how hard is the move later? What has to be reconfigured (registry image path, values in the k8s repo, Vault, CI variables).

**Image build**
- [ ] CI template for build and push to the GitLab registry; which runner.

**Deploy**
- [ ] Where Pitcrew lives: own chart in the registry + values in a stage repo, or own k8s repo with an ArgoCD app.
- [ ] Who can merge there; can I roll a new version myself.
- [ ] Deploy on every merge to the main branch or on a tag.
- [ ] Resources: 1 replica, small CPU / memory limits.

**Secrets**
- [ ] How values get into the pod: External Secrets Operator / Agent Injector / other. The app only reads env vars, it does not talk to the store.
- [ ] Which engine and path for Pitcrew secrets. For the MVP I can use the stage namespace, I have access.
- [ ] Secrets to provision now: LiteLLM key (later), GitLab token, Slack webhook, Allure token (personal for now).

**Network**
- [ ] Egress for: LiteLLM, GitLab API, Allure TestOps (`testops.ston.fi`), Slack hooks. Jira Cloud (`atlassian.net`) later.
- [ ] Egress to the stage UI for Playwright checks of test-ids (GW-7).
- [ ] Ingress from `gitlab-runner` to Pitcrew.
- [ ] Does the service need a DNS name, or is the internal Service address enough for the CI step.
- [ ] Can I call the service from my laptop for testing (VPN, port-forward, internal ingress).

**Storage** (ask now, so DevOps are not bothered again later). Two kinds:
- [ ] Database: MySQL per namespace. Credentials via Vault.
      What persists: rerun state per nightly pipeline (rerun pipeline id, status, timestamps) so a redeploy mid-rerun does not lose or duplicate it; later flake stats and report history.
- [ ] Files: PVC in the namespace for the working directory: test repo clone and worktrees, downloaded Allure reports, Claude sessions (`CLAUDE_CONFIG_DIR` points to a directory on the volume). One replica, `Recreate` strategy.
      Storage class, size (1–5 GB as a starting point: repo 55 MB, worktrees 50–100 MB each, Allure reports up to hundreds of MB), can it be extended later.

**Logs**
- [ ] Logging stack and how to find the service in it. We write JSON to stdout.
- [ ] Log conventions: format, required fields. Ours: `timestamp` (ISO 8601, UTC), `level`,
      `logger`, `message`, then the context (`request_id`, `trace_id`, `step`, `team`,
      `environment`, ...) and `exception` / `exc_type` (ADR 0003).
- [ ] Is `trace_id` linked to Tempo as an OpenTelemetry trace id in Grafana? Ours is the Run
      chain's id, not an OTel one; rename the field if it is.
- [ ] Grafana access.

## LiteLLM

- [ ] Endpoint, available models, rate limits, budget.
- [ ] Anthropic-compatible endpoint (`/v1/messages`) so Claude Code can run against LiteLLM via `ANTHROPIC_BASE_URL`; which Claude models are routed there.
- [ ] Are prompts logged on their side.
- [ ] Key — request when the service is deployed.

## Security

- [ ] Security scans in CI (gitleaks, Trivy) before production.
- [ ] Sending masked logs to LiteLLM: approval needed or internal Bedrock is enough.

## Me and QA (`qa_automation`)

- [ ] CI step that triggers Pitcrew. Auth: a shared secret in `qa_automation` CI/CD variables, checked by Pitcrew.
- [ ] One GitLab token covers everything: cloning over HTTPS, pipelines API (start a rerun with variables, play or retry a job), job logs, branches and MRs. `qa_automation` → Settings → Access tokens, project access token, scope `api` (add `write_repository` if git push over HTTPS complains), role Developer. Self-service; replaced by a service account later. No pipeline trigger token needed.
- [ ] Slack webhook from the repo.
- [ ] Protected branches: confirm MR-only is enough.

## Decided

- No Sentry for now: structured logs in the shared stack are enough.
- Storage from the start, two kinds: MySQL for operational state (rerun state so a redeploy mid-rerun neither loses nor duplicates a rerun) and a PVC for the working directory (test repo clone and worktrees, Allure reports, Claude sessions). The PVC content is mostly a cache except the sessions.
- Claude Code state lives on the PVC via `CLAUDE_CONFIG_DIR` (sessions, settings, memory). Session lookup is keyed by the absolute working directory path, so clone and worktree paths on the volume must be stable.
- Rerun trigger is idempotent by nightly pipeline id; the Run chain state survives a restart in the DB, and the service learns that a rerun finished from the rerun's `night_rerun` CI callback, not by polling GitLab ([ADR 0002](adr/0002-rerun-as-gitlab-pipeline-with-ci-callback.md)).
- Service accounts (GitLab bot, Allure, Jira) come after the MVP is proven and approved, see roadmap.
- Jira integration is a later step, pending approval.
- Local first: the MVP runs from a laptop until the demo; deploy, CI integration and security approval are the rollout phase.
- Exit criteria for rollout: I can ship an image to stage without a ticket, add a secret myself (or via a one-day procedure), logs are visible.

**New service request**
- [ ] Where and how to file the request for a new service, and what it must contain. I can provide up front:
  - service and repo name, link to the Dockerfile, port `8000`, `GET /health` for probes;
  - resources: 1 replica, standard CPU / memory limits;
  - env variables and which of them are secrets (Vault path);
  - MySQL: a database and a user;
  - PVC for the working directory;
  - network: egress to LiteLLM, GitLab API, Allure TestOps, Slack; ingress from `gitlab-runner`;
  - who calls the service and how (CI step in `qa_automation`).
