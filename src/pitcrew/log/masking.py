"""Masking of secrets in the log output and in the Agent's prompt (ground rules: no secret
reaches a log line, none reaches the LLM; ADR 0006)."""

import json
import logging
from collections.abc import Iterable

from structlog.typing import EventDict, WrappedLogger

MASK = "***"

# Shorter values are not masked: they would mask ordinary words and numbers.
MIN_SECRET_LENGTH = 6

# Fields whose value is masked whatever it is, e.g. a header passed to a log line by mistake.
SECRET_FIELD_PARTS = ("token", "authorization", "password", "secret", "webhook")

_secrets: set[str] = set()


def mask_secrets(values: Iterable[str]) -> None:
    """Masks these values from now on wherever they appear in a log line, also inside a
    message, a traceback or an external service's answer, and in the Agent's prompt.
    `Settings` registers every secret it reads, so code that takes secrets from it needs
    nothing more.

    Args:
        values: The secrets; one shorter than `MIN_SECRET_LENGTH` is not masked.
    """
    for value in values:
        if len(value) >= MIN_SECRET_LENGTH:
            _secrets.add(value)
            # As JSON writes it, should the value hold a quote or a backslash.
            _secrets.add(json.dumps(value)[1:-1])


def masked(text: str) -> str:
    """The text with every registered secret replaced by `MASK`.

    Args:
        text: Text bound for a log line (e.g. before it is cut short) or for the LLM (the
            Agent's prompt).
    """
    # Longest first: a secret that holds another one is masked whole.
    for secret in sorted(_secrets, key=len, reverse=True):
        text = text.replace(secret, MASK)
    return text


def mask_secret_fields(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """structlog processor: masks the value of a field named like a secret."""
    for key in event_dict:
        if any(part in key.lower() for part in SECRET_FIELD_PARTS):
            event_dict[key] = MASK
    return event_dict


class MaskingFormatter(logging.Formatter):
    """Masks the known secrets in the formatted line: the last step before the output, so no
    renderer, library or traceback gets around it."""

    def __init__(self, formatter: logging.Formatter) -> None:
        """
        Args:
            formatter: Renders the line before it is masked.
        """
        super().__init__()
        self._formatter = formatter

    def format(self, record: logging.LogRecord) -> str:
        return masked(self._formatter.format(record))
