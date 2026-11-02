# Structured logging: structlog, JSON on stdout, context in a log scope, secrets masked at the output

Pitcrew logs through `structlog` over the stdlib `logging`, set up once in `pitcrew.log`. One
handler on stdout renders every line, ours and the libraries' ones (uvicorn, alembic, httpx):
one JSON object per line at deploy (`LOG_FORMAT=json`, the default), coloured console lines
locally (`make run` sets `LOG_FORMAT=console`). The cluster's log stack picks JSON on stdout up by
itself (`docs/deploy-questions.md`), so nothing in the service knows about Grafana or Loki.
A plain stdlib setup with a JSON formatter was the alternative; structlog gives the processor
chain (context, renaming, masking, rendering) and both renderers ready-made.

Every line carries the context of what it was written for, without the code passing it:
`request_id` for a request, the trigger (`step`, `team`, `environment`, `pipeline_id`,
`launch_id`), the Run chain's `trace_id` and the Step's current `activity`. It lives in a *log
scope* (`log_scope`, `bind_log_context`), a mutable dict held in a context variable, rather than
in structlog's own `bind_contextvars`. A sync endpoint and a background Step run in a copy of the
context, so a value they set would be lost to the code around them; the dict is shared by the
copies, so the trace id bound in `accept` also reaches the request's log line. A Step run opens a
scope of its own from the Run chain, so its lines do not depend on how the background task was
started. The field is named `trace_id` as in `CONTEXT.md`, although it is not an OpenTelemetry
trace id; if Grafana links `trace_id` to Tempo, it is renamed in one processor.

A failed Step is logged once, with its context and the exception, and not re-raised: the caller
has had its answer, and uvicorn would only print the traceback again without the context. For
the same reason uvicorn's access log is off and `Exception in ASGI application` is filtered out:
`RequestLogMiddleware` writes the request line and the request's error with the context.

Secrets are masked by value on the formatted line, the last step before the output: every secret
`Settings` reads registers itself, so a token in a message, a traceback or an external service's
answer is masked whatever wrote it. Fields named like a secret (`token`, `authorization`, ...)
are masked whatever their value. httpx and SQLAlchemy are kept at WARNING: httpx writes every
request URL, a Slack webhook among them.
