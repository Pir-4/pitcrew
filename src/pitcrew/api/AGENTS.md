# api/

HTTP only: parse the request, call a Step or a repository, shape the answer. Domain decisions
live in `steps/`.

| Module | Holds |
|--------|-------|
| `triggers.py` | `POST /triggers` |
| `run_chains.py` | `GET /run-chains/{trace_id}`: the Step running now and what it is doing (`failed` when it failed), `failure_reason` (why, masked and cut short; `None` otherwise), `runs` (each Run in the order it was started: kind, pipeline, launch, expected and Failed test counts, Run outcome and reason), the Error groups and the Conclusion (its `posted_at` read from the chain's `conclusion` post) |
| `schemas.py` | Request and response bodies |
| `auth.py` | The bearer token (`PITCREW_TRIGGER_TOKEN`) |
| `exception_handlers.py` | `EXCEPTION_HANDLERS`: exception → HTTP answer and its log line, registered on the app in `main.py` |
| `middleware.py` | `RequestLogMiddleware`: one log line per request and its log scope |
| `dependencies.py` | What endpoints take from the app state `main.lifespan` prepared |

## Rules

- One router module per resource, included in `main.py`. Every endpoint but `/health` depends
  on `require_trigger_token`.
- `POST /triggers` knows no particular Step: it takes the Team config (`TeamConfigs.get`, the
  Team in any spelling; from there on the config's `name` is the Team's spelling) and
  the Step's class (`registry.step_class`), calls the class's `accept` before answering (no
  Step instance exists yet), starts the class's `run(chain_id, team_config, deps)` in
  `BackgroundTasks` and answers with the Run chain's trace id (`202`, or `200` when the
  Step has already finished).
- Errors become HTTP answers only in `exception_handlers.py`, never in an endpoint: an
  endpoint holds no `try` / `except` and imports no client exception; it lets the exception
  through. The one exception is an endpoint's own resource not found
  (`GET /run-chains/{trace_id}`): `HTTPException(404)` raised in the endpoint.
  `UnknownTeamException` → `422` naming the Team (the trigger's Team is any string:
  the request's validation knows no Teams, so this is the only check of it),
  `StepNotImplementedException` → `501`, `StepException` → `422` with its `reason` (warning
  `Trigger rejected` with its `details`),
  TestOps' `UnauthorizedException` (Pitcrew's own token) → `502` (error log line). The body is
  `{"detail": ...}`, as FastAPI's own errors. A new rejection is a domain exception raised
  where it is found plus a handler here; its status still goes into the route's
  `responses=`.
- An endpoint takes everything through a getter of `dependencies.py`. A new client (or
  `WebLinks`, `get_links`) gets a getter there and goes into `StepDependencies` through
  `get_step_dependencies`, so that a test
  overriding the client in `app.dependency_overrides` reaches the Steps too.
- Data goes through `Repositories` (`get_repositories`); an endpoint builds no query and touches
  no `Session`.
- `steps/` never imports `api/`: a request body extends the Steps' own type
  (`TriggerRequest(Trigger)`).
- A response body is built from the model by a `from_<model>` classmethod. A status of the
  model is its enum already (`run.kind`, `chain.activity`): it goes into the body as it is,
  never converted from a string. A field whose
  meaning the name does not carry gets `Field(description=...)`, so that OpenAPI shows it.
- Every status other than the default is listed in the route's `responses=`.
- An endpoint binds what identifies its request with `bind_log_context(...)`;
  `RequestLogMiddleware` writes the one request line with it.

## Tests

Through the `pitcrew` driver in `tests/test_run_chain/` (see its `AGENTS.md`).
