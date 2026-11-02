"""Logging of the service (ADR 0003): structlog, JSON on stdout at deploy, console lines
locally, the request or Run chain context on every line, secrets masked."""

from structlog.stdlib import get_logger

from pitcrew.log.context import bind_log_context, log_scope
from pitcrew.log.masking import mask_secrets, masked
from pitcrew.log.setup import LogFormat, configure_logging
from pitcrew.log.timing import Stopwatch

__all__ = [
    "LogFormat",
    "Stopwatch",
    "bind_log_context",
    "configure_logging",
    "get_logger",
    "log_scope",
    "mask_secrets",
    "masked",
]
