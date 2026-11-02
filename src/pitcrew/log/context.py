"""The fields every log line carries without the code passing them: the context of the
request or of the Run chain the line was written for (ADR 0003)."""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from structlog.typing import EventDict, WrappedLogger

# One mutable dict per scope. A sync endpoint and a background task run in a copy of the
# context, so a new value set there would not reach the code around them (the request log
# line); the dict object is shared by the copies, so what they add to it does.
_scope: ContextVar[dict[str, Any] | None] = ContextVar("log_scope", default=None)


@contextmanager
def log_scope(**fields: Any) -> Generator[None]:
    """Opens a scope of log context: every line written inside carries `fields`, the fields of
    the enclosing scope, and whatever `bind_log_context` adds later. A request and a Step run
    each open one.

    Args:
        **fields: The context of the new work, e.g. `step=...`.
    """
    token = _scope.set((_scope.get() or {}) | fields)
    try:
        yield
    finally:
        _scope.reset(token)


def bind_log_context(**fields: Any) -> None:
    """Adds fields to every later line of the current scope, including the lines the code
    around writes after (the request log line gets the trace id bound by the Step). Outside
    any scope it does nothing.

    Args:
        **fields: The context learnt within the scope, e.g. `trace_id=...`.
    """
    scope = _scope.get()
    if scope is not None:
        scope.update(fields)


def merge_log_context(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """structlog processor: puts the current scope's fields into the line; the line's own
    fields win."""
    return {**(_scope.get() or {}), **event_dict}
