# db/

Run chain state through SQLAlchemy 2 to `DATABASE_URL`: SQLite locally, MySQL at deploy. What a
model, a transition or a repository does is in its docstring; this file holds where things live
and the rules a change must keep.

`models/` is the domain model: the entities, their transitions and their value types (the
enums, frozen values such as `RunVerdict` and `NewErrorGroup`). There is no separate domain
package and none is started. `repositories/` and `services/` only load and store the models and
define no type of the domain.

| Path | Holds |
|------|-------|
| `models/run_chain.py` | `RunChain` with its transitions, `Activity` |
| `models/run.py` | `Run`, `RunKind`, `RunOutcome`, `RunVerdict` |
| `models/post.py` | `Post`, `PostKind`: a Slack post about a chain |
| `models/error_group.py` | `ErrorGroup`, `ErrorGroupTest`, `ErrorKind`, `NewErrorGroup` / `NewErrorGroupTest` (recognized, not stored yet) |
| `models/base.py` | `Base` with `NAMING_CONVENTION`, `TimestampMixin`, `utc_now`, `enum_type` |
| `models/exceptions.py` | `RunChainException`: a transition refused |
| `repositories/` | One `<Table>Repository(BaseRepository[Model])` per table; `container.py` with `Repositories` |
| `services/` | Storage across several tables (`ErrorGroupService`) |
| `migrate.py`, `migrations/` | Alembic, applied on startup |

## The Run chain

- A Run chain's Runs are `Run` rows and its Slack posts are `Post` rows, never columns of
  `run_chains`. A new kind of Run is a `RunKind` member, a new kind of post a `PostKind` member
  (keyed when a chain has several, e.g. one per fix MR): a row, not a migration of columns.
- Invariants held by unique constraints: one Run of each kind per chain, a pipeline in at most
  one Run across all chains (so a trigger's pipeline finds one chain), one post per chain, kind
  and key. A chain is found by the pipeline of any of its Runs; the caller checks the kind.
- The chain moves only through the transition methods of `RunChain`. They call no client and do
  not commit; the caller saves after every one (`RunChainRepository.save`), so that
  `GET /run-chains/{trace_id}` shows the chain live and a resumed Step starts from it.
- A new move of the chain is a new method of the model that holds its invariant
  (`start_rerun` refuses a second Rerun), never a write from outside. A `Run` has no setters:
  what judging finds goes onto it only through `record_judgement`.
- `record_judgement` writes the verdict and moves the chain in one transition, so that a
  failure in between cannot leave one without the other. A Run that ends the chain moves to
  `posting_conclusion`, never straight to `done`: the Step finishes with `record_conclusion`.
- Transitions a repeated trigger may replay are idempotent (`accept_rerun_launch` keeps the
  first launch); `set_activity` clears `failure_reason`, so a Step running again is no longer
  failed.
- Whether a Step has finished is not stored: `RunChain.has_finished` tells it from the current
  Step and activity, by the order of `constants.Step`.
- `RunChainRepository` holds no transition and builds no state: lookups,
  `get_or_create_for_nightly_run` (concurrency-safe) and `save`, the one commit. No per-field
  `record_*` / `finish_*` method comes back.

## Rules

- The schema changes only by a new Alembic migration in `migrations/versions/`:
  `uv run alembic revision --autogenerate -m "..."`, then edited by hand where data has to move.
  An earlier migration is never rewritten.
- A migration that alters a table of SQLite does it inside `op.batch_alter_table`; constraints
  are dropped by the name `NAMING_CONVENTION` gives.
- A migration that moves data moves it in both directions, the downgrade restoring the old
  shape from the new rows (`0007_create_runs.py` is the example). It reads and writes through
  `sa.table(...)` of its own, never through the ORM models, which follow the latest schema.
- An enum member of a status column renamed or merged is a migration that moves the stored
  values (`0008`), so that old chains still read; a member added needs none.
- A status column is typed by its enum: `mapped_column(enum_type(RunKind, 16))`, the length
  being the column's in the migrations (`alembic check` shows no difference after a change of
  the models that changes no schema). Nobody converts a stored status from a string or writes a
  plain string into one. The chain's `team` stays a string: a Team is any name with a Team
  config.
- Every query and commit of a table lives in its repository. Everyone else reaches the DB
  through `Repositories` (`with Repositories(session_factory) as db: ...`); a new repository or
  service gets a property there.
- Work across several tables goes into a service in `services/`, which commits once.
- Timestamps are UTC (`TimestampMixin`, `utc_now`).
- The meaning of a column or an enum member the name does not carry goes into the model's
  docstring, under `Attributes:`.

## Tests

Through the Steps and the API in `tests/test_run_chain/`, on SQLite. A transition whose
behaviour HTTP cannot show (a launch accepted again) is tested on a `RunChain` held in memory,
in `tests/test_db/`; so is a rule the DB itself holds (a unique constraint, a status none of its
enum's values), saved through `Repositories` into a fresh SQLite file migrated as at startup.
