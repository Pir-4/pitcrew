# Pitcrew

Pitcrew takes over the routine after the nightly test run of `qa_automation`: it reruns failed
tests, filters out flakes and reports its conclusions to the team.

## Language

### Run chain

**Run chain**:
The sequence of Runs Pitcrew drives for one night of one Team: the Nightly run, then the
Rerun, ended by the Conclusion. Only the nightly chain exists for now.
_Avoid_: flow, workflow

**Trace id**:
The id of one Run chain: every trigger of the chain is answered with it, every log line of its
Steps carries it, and the status of the chain is read by it.
_Avoid_: run id, chain id

**Step**:
The stage of the Run chain a trigger comes from (`night_run`, `night_rerun`); tells Pitcrew what
has just finished and what to do next.
_Avoid_: stage, phase

**Run**:
One `qa_automation` pipeline of a Run chain and the Allure launch it produces, which Pitcrew
judges. A Run is a Nightly run or a Rerun; each ends with a Run outcome.
_Avoid_: pipeline (when the launch is meant too), test run

**Nightly run**:
The Run of the scheduled `qa_automation` pipeline of a Team; it starts the Run chain.
_Avoid_: night run, main run

**Rerun**:
The Run Pitcrew starts on the same Environment that runs only the Failed tests of the Nightly
run.
_Avoid_: retry, restart

**Run outcome**:
Pitcrew's verdict on a finished Run: **green** (no Failed tests), **with failures**
(the run happened and some tests failed) or **broken** (the tests did not actually run, or the
Environment is likely down: the pipeline stopped before its `test` job finished, the launch
holds far fewer results than the nightly test plan has test cases, e.g. only the data
preparation result, or too large a share of its results are Failed tests). Only *with
failures* leads to a Rerun; a broken one gets a Conclusion saying why. A Rerun is judged by the
same rules, against the test cases written into the Rerun test plan and without the share of
Failed tests: it runs only Failed tests, so many of them failing again is no sign of a down
Environment.
_Avoid_: run status, passed / not passed

**Failed test**:
A test result with Allure status `failed` (an assertion failed) or `broken` (an exception or
setup error).

**Rerun test plan**:
The single Allure TestOps test plan per Team, created by hand and named in the Team config,
whose test cases Pitcrew overwrites with the Failed tests before each Rerun.

**Error group**:
The Failed tests of a Rerun that fail for one cause Pitcrew recognizes with certainty, keyed
by Error kind and the name of what broke (e.g. one model). Pitcrew reports only Error groups;
the Failed tests it does not recognize are only counted. An Error group is the unit of a fix:
its tests are the ones to run again once it is fixed.
_Avoid_: defect (an Allure TestOps object), error, failure cluster

**Error kind**:
The sort of cause behind an Error group. Only **model** for now: a model of the tests (an API
response schema or a database model) rejected the data it was given.
_Avoid_: error type, category (an Allure TestOps object)

**Conclusion**:
Pitcrew's own Slack post about a Run chain, one per chain: a broken Nightly run and why; or,
after the Rerun, how many tests failed at night and which still fail on the Rerun (or that the
Rerun is broken), and the Error groups among the tests that still fail; later links to fix
MRs. It complements the pipelines' own
Slack notifications, it does not replace them.
_Avoid_: report, summary, notification

### Agent

**Agent**:
Claude Code, run by Pitcrew to work on the code of the test repo. Pitcrew decides what the
Agent is given and what it may do; the Agent does the code work.
_Avoid_: bot, LLM, Claude (as the name of the role)

**Agent task**:
One run of the Agent: a prompt, the tools it may use, its limits (turns, budget, timeout) and its
Working copy; it ends with an outcome (success, turn limit, budget limit, timeout or error), an
answer when it succeeded, and a session.
_Avoid_: job (a GitLab object), run (a Run is a pipeline Pitcrew judges)

**Working copy**:
A worktree of `qa_automation` at the ref an Agent task needs, without the repo's Claude Code
settings, given to that one Agent task.
_Avoid_: checkout, clone

**Model tier**:
How strong a model an Agent task needs: **junior**, **middle** or **senior**. Each tier is one
model of the LiteLLM pool named in the service env; what the Agent task is for decides its
tier (asking about the repo: junior).
_Avoid_: model size, Haiku / Sonnet / Opus (as the names of a tier)

### Configuration

**Team**:
A test team of `qa_automation`, named as its `PROJECT_NAME` (e.g. Gateway, Wallet); the unit
Pitcrew is configured for. Pitcrew works for a Team that has a Team config, which spells its
name as `qa_automation` does; a trigger may spell it otherwise (`gateway`), Pitcrew always
uses the Team config's spelling.
_Avoid_: project (ambiguous with Allure and GitLab projects)

**Environment**:
The stand the tests run against (e.g. staging, testnet). It comes with each trigger and
is not part of the Team config; a Rerun always runs on the Environment of its Nightly run.
_Avoid_: stage, stand

**Team config**:
The non-secret settings of one Team (Allure project, Rerun test plan, Slack channel, enabled
features), layered over a base config.
