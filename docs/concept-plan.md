# Pitcrew — Concept and Plan

Oct 8, 2026 · @Valentin Agapitov

## Overview

Pitcrew is an AI service that takes over the routine work after the nightly run: it reruns failed tests, filters out flakes, classifies real failures, highlights likely bugs, and proposes test fixes via MRs. By morning, the team gets an analyzed run instead of a list of red tests.

The service works for one team, Gateway, whose API the nightly run covers; another team is a config file. It starts as a single service with internal roles and scripts; splitting into multiple services happens later, as needed.

**The problem.** Rerunning and analysis are currently manual. A rerun blocks the environment, and with a large number of failures, triage takes up to \~3 hours. A significant share of failures are small things like a changed test-id or schema, which an agent can handle on its own.

**Why run analysis rather than test generation as the first step:**

- The pain is measurable: hours spent on triage and environment blocking time give a clear baseline for comparison.
- Almost everything is within our perimeter: CI and Allure are already available, models are accessible via the company LiteLLM proxy, and we only need deployment from DevOps.
- No inbound triggers from cloud Jira into the internal perimeter are needed: Pitcrew only reads Jira using a token.
- It works for the whole team automatically, without changing habits, and easily extends to other teams.
- It is the foundation for test generation: an agent that fixes models, schemas, and locators needs the same understanding of the harness as a generator does.

## Goals and Metrics

The MVP is successful if morning run triage shrinks from hours to minutes and Pitcrew's classifications can be trusted without rechecking every failure. The baseline must be collected before launch, otherwise there is nothing to compare against; the target values below are reference points for discussion.

| Metric | How to measure | Baseline | Target |
| --- | --- | --- | --- |
| Developer time spent on run triage, h | Self-reporting for 2–4 weeks before and after | up to \~3 h on bad days, average — to be collected | < 30 min |
| Classification accuracy, % | Backtest on historical failures from Allure, then spot checks in production | — | ≥ 80% |
| Environment blocking time by runners during working hours, h | Rerun time from CI | to be collected | ≈ 0: rerun before the workday starts |
| Share of flakes filtered out without a human, % | Pitcrew reports | — | collect statistics |
| Share of accepted Pitcrew MRs, % | Merged MRs / created | — | ≥ 70% |

## MVP Scope

The MVP is planned for roughly two months and covers the entire morning cycle: rerun, analysis, and small fixes via MRs. Fixes reach the repo only after review by the team, so the risk of breaking something stays low.

**In scope:**

- Automatic trigger when the nightly CI run completes.
- Rerun of only the failed tests on the same environment, right after the run, while the environment is free.
- Classification of each failure with an explanation and links (Allure, logs, sprint tasks).
- Linking failures to current-sprint tasks in Jira and to commits in the test repo since the last green run. Pitcrew has no access to the application code.
- A summary posted to the team channel, grouped by class.
- MRs with small drift fixes: test-ids and locators; schemas and models — only when a sprint task explains the change.

**Deliberately out of scope:**

- Fixes to test logic and new checks — these remain with the team.
- Upgrading outdated libraries — stage 2.
- Generating tests from Jira tasks — stage 3.
- Automatic bug filing.

**Order within the MVP:** rerun and report first; MRs are enabled once classification has proven its accuracy on real runs.

## How It Works

&#91;embedded content: Pitcrew flow · from run to summary\]

Flakes are filtered out by the rerun before analysis, so the agent only analyzes consistently failing tests. Everything comes together in a single morning summary with links to details.

## Classification and Auto-fix Rules

Each failure falls into one of five classes; Pitcrew is only allowed to fix test drift itself, and only via an MR.

| Class | Signals | Pitcrew action | Decides |
| --- | --- | --- | --- |
| Flake | Passed on rerun; unstable per Allure history | Marks it, tracks instability statistics | The team: whether to fix the test |
| Environment | Timeouts, 5xx from dependencies, service unavailable, many failures with one cause | Groups by cause, reports | QA / DevOps |
| Test drift | A test-id, schema, or model changed, and there is a sprint task that explains it | Creates an MR with the fix | The on-duty developer reviews the MR |
| Likely bug | Behavior changed, but no sprint task explains it; the test's expectation looks correct | Highlights it with evidence and related sprint tasks | The on-duty developer files a bug |
| Unsure | Signals contradict each other or context is insufficient | Hands it to a human with whatever it has gathered | The on-duty developer |

**Non-negotiable rules:**

- Never pushes to the main branch — only an MR reviewed by a human.
- Edits a schema, model, or expectation only if it has found a task in the current sprint that explicitly describes this change, and references it in the MR. No such task — it's a bug candidate, not a fix candidate.
- Does not weaken assertions, delete tests, or add skips or retries.
- Every decision comes with an explanation and links so it can be verified in a minute.
- Secrets (keys, tokens, passwords) are masked before anything reaches the LLM. Stage test data is sent as is: it holds no customer data, and the models run only through the internal LiteLLM on AWS Bedrock (ADR 0006).

## Architecture

&#91;embedded content: Pitcrew architecture · roles and integrations\]

We start with a single service: roles are modules and scripts inside it, and a new task (library upgrades, test generation) is added as a new role. A role should be extracted into a separate service only when it needs its own trigger, access, or scale. Dashed lines show what is not in the MVP.

## Roadmap

&#91;embedded content: Pitcrew roadmap · 6 stages, 3 gates\]

The maintained version of the roadmap lives in [roadmap.md](roadmap.md).

Timelines are not fixed yet: moving to the next stage is decided by a gate, not a date. Stages 2–4 are a direction, not a commitment; they show that the service grows beyond run analysis.

## Dependencies and Risks

There are few external dependencies for the MVP: deployment from DevOps and a LiteLLM key. The Jira token already exists.

**What we need from other teams:**

- DevOps — service deployment, CI API tokens (triggering reruns, reading logs), a hook on nightly run completion.
- LiteLLM — a key for the proxy (Claude models via AWS Bedrock).
- Jira — a read token already exists (personal for now); requests go from inside to the cloud, no inbound triggers.

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Auto-fix masks a bug | The test is adjusted to broken behavior, the bug ships to prod | Fix only when a sprint task explains the change; always via MR review |
| Data leaks to the LLM | Secrets or customer data end up in prompts and model logs | Models only via internal LiteLLM on AWS Bedrock; masking before sending |
| Rerun still blocks the environment | The problem is merely shifted in time | Rerun right after the run; don't blindly rerun known flakes from history |
| Noisy reports | The team stops reading them | Short summary on top, details behind links; grouping by cause |
| Low accuracy at launch | Loss of trust from the first week | Backtest before launch; an "unsure" class instead of a confident mistake |
| LLM cost during mass failures | Expensive nights when the environment is down | Cheap grouping by error first, then only one representative per group goes to the LLM |
| No access to application code | A Jira task may not describe an API change: the agent may mistake a bug for drift or vice versa | Compare API responses with the last green run using Allure attachments; if the task and the facts disagree — "unsure" class |

## Open Questions

Stages 0–1, the backtest and an MVP of about two months, are what the team agreed to try: fixes don't reach the repo without review, so the risk is low, and time savings are visible from the first weeks.

- [ ] Get a LiteLLM key.
- [ ] Where to deploy the service, and who from DevOps will help?
- [ ] Which CI is used, and which of its APIs are available for triggering reruns and reading logs?
- [x] Jira API read token — available (personal for now).
- [x] Rerun — on the same environment right after the main run (confirmed).
- [ ] Where to send the report: one shared channel or a channel per team?
- [ ] Collect a 2–4 week baseline of triage time.
- [ ] Label historical failures from Allure for the backtest: what each one actually turned out to be.
