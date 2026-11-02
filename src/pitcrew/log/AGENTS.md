# log/

One logging setup for the process (ADR 0003). How to log from the rest of the code: the
**Logging** section of the root `AGENTS.md`. This file is for changing the package itself.
Callers import from `pitcrew.log`.

| Module | Holds |
|--------|-------|
| `setup.py` | `configure_logging`: structlog renders every line, ours and the stdlib ones, as JSON or console lines through one handler |
| `context.py` | `log_scope`, `bind_log_context`: the fields every line of a scope carries |
| `masking.py` | `mask_secrets`, `masked`, `MaskingFormatter`: secrets masked on the output; `masked` also masks the Agent's prompt (ADR 0006) |
| `timing.py` | `Stopwatch` |

## Rules

- `MaskingFormatter` stays the last step before the output, so that no renderer, library or
  traceback gets around it. A new renderer goes inside it, never beside it.
- `mask_secret_fields` stays in both renderer chains; a new field name that holds a secret goes
  into `SECRET_FIELD_PARTS`.
- A scope is one mutable dict shared by the copies of the context, so that what a background
  task or a sync endpoint binds reaches the request's own line. Keep it so when changing
  `context.py`.
- `configure_logging` may be called again (the tests do): it replaces its handler, never adds a
  second.
- A chatty library goes into `QUIET_LOGGERS`.

## Tests

What is logged is asserted through the `logs` fixture, including that no secret appears
(`tests/test_run_chain/test_logging.py`).
