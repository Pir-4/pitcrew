import io
import json
from typing import Any


class Logs:
    """What the service logged, as the deploy writes it: one JSON object per line."""

    def __init__(self) -> None:
        self.stream = io.StringIO()

    @property
    def text(self) -> str:
        return self.stream.getvalue()

    def lines(
        self, logger: str = "pitcrew.", debug: bool = False
    ) -> list[dict[str, Any]]:
        """The lines of the loggers whose name starts with `logger`, DEBUG ones left out
        unless `debug`."""
        return [
            line
            for line in map(json.loads, self.text.splitlines())
            if line["logger"].startswith(logger) and (debug or line["level"] != "debug")
        ]

    def messages(self, logger: str = "pitcrew.") -> list[str]:
        return [line["message"] for line in self.lines(logger)]
