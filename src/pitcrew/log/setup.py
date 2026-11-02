"""One logging setup for the service and the libraries it runs on: structlog renders every
line, ours and the stdlib ones (uvicorn, alembic, httpx), as JSON at deploy or as coloured
console lines locally (ADR 0003)."""

import logging
import sys
from enum import StrEnum
from typing import IO, Any

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

from pitcrew.log.context import merge_log_context
from pitcrew.log.masking import MaskingFormatter, mask_secret_fields


class LogFormat(StrEnum):
    """How log lines are rendered.

    Attributes:
        JSON: One JSON object per line on stdout: what the cluster's log stack picks up.
        CONSOLE: Coloured lines for a human, e.g. `make run`.
    """

    JSON = "json"
    CONSOLE = "console"


LEADING_FIELDS = ("timestamp", "level", "logger", "message")

# Libraries too chatty below WARNING: httpx writes every request URL (a Slack webhook among them),
# SQLAlchemy every statement.
QUIET_LOGGERS = ("httpx", "httpx2", "httpcore", "sqlalchemy")

_SHARED: list[Processor] = [
    merge_log_context,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
]

# The handler `configure_logging` installed; replaced, never added twice.
_handler: logging.Handler | None = None


def configure_logging(
    log_format: LogFormat, level: str, stream: IO[str] | None = None
) -> None:
    """Sends every log line through one handler on `stream` (stdout by default). Called when
    the app is imported, after uvicorn has set up its own loggers, so their lines go the same
    way. May be called again (the tests do) to change the format, level or stream.

    Args:
        log_format: JSON at deploy, console lines locally.
        level: The lowest level written, e.g. `INFO`.
        stream: Where the lines go; stdout when `None`.
    """
    global _handler
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(
        MaskingFormatter(
            structlog.stdlib.ProcessorFormatter(
                foreign_pre_chain=_SHARED,
                processors=_renderers(log_format),
            )
        )
    )
    root = logging.getLogger()
    if _handler is not None:
        root.removeHandler(_handler)
    root.addHandler(handler)
    root.setLevel(level)
    _handler = handler

    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    uvicorn_error = logging.getLogger("uvicorn.error")
    if _skip_asgi_exception not in uvicorn_error.filters:
        uvicorn_error.addFilter(_skip_asgi_exception)
    # `RequestLogMiddleware` writes one line per request instead, with its context.
    logging.getLogger("uvicorn.access").disabled = True
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *_SHARED,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def _renderers(log_format: LogFormat) -> list[Processor]:
    if log_format == LogFormat.CONSOLE:
        return [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            mask_secret_fields,
            structlog.dev.ConsoleRenderer(),
        ]
    return [
        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
        _add_exc_type,
        structlog.processors.format_exc_info,
        structlog.processors.EventRenamer("message"),
        mask_secret_fields,
        _leading_fields_first,
        structlog.processors.JSONRenderer(default=str),
    ]


def _add_exc_type(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """The exception's class apart from its traceback, to filter the lines by it."""
    exc_info: Any = event_dict.get("exc_info")
    if exc_info is True:
        exc_info = sys.exc_info()
    if isinstance(exc_info, BaseException):
        event_dict["exc_type"] = type(exc_info).__name__
    elif isinstance(exc_info, tuple) and exc_info[0] is not None:
        event_dict["exc_type"] = exc_info[0].__name__
    return event_dict


def _leading_fields_first(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    leading = {key: event_dict.pop(key) for key in LEADING_FIELDS if key in event_dict}
    return {**leading, **event_dict}


def _skip_asgi_exception(record: logging.LogRecord) -> bool:
    """uvicorn's `Exception in ASGI application` repeats the error `RequestLogMiddleware` has
    already written with the request's context."""
    return not record.getMessage().startswith("Exception in ASGI application")
