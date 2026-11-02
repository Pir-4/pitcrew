from time import perf_counter


class Stopwatch:
    """Times a piece of work for its log line's `duration_ms`; starts when created."""

    def __init__(self) -> None:
        self._started = perf_counter()

    @property
    def ms(self) -> int:
        """Milliseconds since the start."""
        return round((perf_counter() - self._started) * 1000)
