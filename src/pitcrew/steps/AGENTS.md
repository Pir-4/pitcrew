# steps/

The Steps of the Run chain (`CONTEXT.md`) and the domain rules they apply. What a function does
is in its docstring; this file holds where things live and the rules a change must keep.

| Module | Holds |
|--------|-------|
| `base.py` | `BaseStep`: `accept`, `run` (the one entry point) and the helpers every Step shares |
| `night_run.py`, `night_rerun.py` | One Step each: `NightRunStep`, `NightRerunStep` |
| `registry.py` | `STEPS`, Step → class, and `step_class` |
| `dependencies.py` | `StepDependencies`: the session factory, the clients, `WebLinks` |
| `trigger.py` | `Trigger`: what a Step is given, whatever brought it |
| `checks.py` | The checks of a trigger run in `accept`, before it is answered |
| `judging.py` | `judge_run` and `Judgement`: judging a Run |
| `outcome.py` | The rules of a broken run, pure functions |
| `error_groups.py` | The Error group rules, one strict rule per Error kind (ADR 0004) |
| `conclusion.py` | `conclusion_message`: the Conclusion, a pure function |
| `publisher.py` | `Publisher`: the one way a Step posts to Slack |
| `exceptions.py` | `StepException` (a trigger Pitcrew may not handle) and `StepNotImplementedException`; `api/exception_handlers.py` answers them |

## A Step

- One module and one class per Step, `<Name>Step(BaseStep)`, an instance per execution on one
  Run chain. It implements only the class method `_chain_for` and `_scenario`. No private
  per-run class, no method that only forwards to another. A new Step is registered in `STEPS`
  and in `constants.Step`, in the order the chain goes through it (`has_finished` relies on it).
- `_scenario` reads as the Step's phases: `_doing(Activity.<X>)`, `judge_run`, a branch on
  `judgement.outcome` (never on whether a reason is set), then `_record` and the next phase.
  A run of transitions and saves inline in `_scenario` is extracted into a named method.
- A helper both Steps would write goes into `BaseStep`; a phase of one Step stays in its class.
- `BaseStep.run` is the one entry point, whatever runs the Step (`BackgroundTasks` now, the
  executor of #32 later). A Step catches nothing: `run` logs a failure once and records it
  masked. Anything more to do on a failure goes there, never into a Step.
- `accept` runs before the trigger is answered: the checks of `checks.py` and finding or
  recording the Run chain, nothing else. A new chain takes its Team from `team_config.name`,
  never from `trigger.team`.
- A Step moves the chain only through the transitions of `RunChain` (`db/AGENTS.md`) and saves
  right after each one. The Step decides what happens; the model, which state follows.
  Whether a Step has finished is asked of the model (`has_finished`), never stored in a Step.
- A Step reads and records a Run through the chain's Run rows (`chain.nightly_run`,
  `chain.rerun`), never through columns of the chain.
- Every action is safe to repeat, since a failed Step runs again from its start on a repeated
  trigger: the check guarding a side effect stays in the Step before it and reads the model
  (no Rerun created when `chain.rerun` exists, no errors read when the chain has its Error
  groups, no post the chain has). The model holds the invariant behind the check, so a missed
  check fails loudly instead of writing twice.
- A new phase gets a new `Activity` member and starts with `_doing`; a phase a transition moves
  the chain into is bound to the log context after the save.
- A value type of the domain comes from `db/models/`; a status read from a model is its enum
  already, never converted from a string.
- A Step reaches the DB only through `Repositories` and a service only through
  `StepDependencies`; a new client goes there. A web link comes from `deps.links`, never built
  in a Step or the Conclusion.

## Judging a Run

- A Step never reads a Run's pipeline or launch nor wires a rule's parameters: it hands its Run
  to `judge_run` and records the `verdict` with `chain.record_judgement`.
- The judgement is recorded before any side effect that follows from it (`night_run` before it
  starts the Rerun, passing `starting_rerun=True`), so a Step failing on the way leaves it
  recorded and resumes from there.
- The order of the checks and the rules of each kind of Run live only in `judge_run`. A new
  kind of Run gets its branch there, never a copy of the order in a Step. `judge_run` may call
  the clients and records nothing.
- A decision of the domain is a plain function of its rules module, called with what was read:
  the rules of a broken run only by `judge_run`, the Error group rules by the Step.

## The Conclusion

- `conclusion_message` is pure: no client, no log, no post. It chooses which Conclusion from the
  Runs' stored outcomes; a Step only calls it once its last Run is judged. A change to its
  text changes the posts that `tests/data/conclusions.py` pins byte for byte.
- Both Steps conclude through `BaseStep._conclude`: build, publish, `record_conclusion`, save.
- `Publisher.publish` is the gate and the record of every Slack post. A new `PostKind` is one
  entry of `_KINDS` (its feature and its log phrases), never a second way to post.
- The `Publisher` neither saves nor moves the chain. A post is at least once, on purpose (no
  idempotency key on a webhook; a lost Conclusion is worse than a doubled one): never "fix"
  it into at most once.

## Tests

The rules, `conclusion_message` and the `Publisher` directly in `tests/test_steps/` (rule
tables; the Conclusion on a chain held in memory with no client); a Step end to end through the
`pitcrew` driver in `tests/test_run_chain/` on a recorded night, never a Step class, its entry
point or a `BaseStep` helper called directly. `judge_run` has no tests of its own: its order
and its per-kind rules show through the Steps.
