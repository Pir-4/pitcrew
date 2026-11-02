"""The rules that put a Failed test into an Error group (ADR 0004): one strict rule per Error
kind on the error of the test, never a looser one."""

import re
from collections.abc import Iterable

from pitcrew.clients.testops import TestResult
from pitcrew.db.models.error_group import ErrorKind, NewErrorGroup, NewErrorGroupTest

# The first line pydantic writes when a model rejects the data; the model as written, generics
# included, e.g. `DataResponse[RoutersOverview]`.
_MODEL_RULE = re.compile(
    r"^pydantic_core\._pydantic_core\.ValidationError: "
    r"\d+ validation errors? for (?P<model>\S+)$"
)


def recognize_error_groups(
    failed_tests: Iterable[tuple[TestResult, str | None]],
) -> list[NewErrorGroup]:
    """The Error groups among Failed tests, largest first; a test no rule recognizes is in
    none. The status of a test does not matter.

    Args:
        failed_tests: Each Failed test with its error message, `None` when it has none.
    """
    groups: dict[tuple[ErrorKind, str], list[TestResult]] = {}
    for test, message in failed_tests:
        if (key := _model_key(message)) is not None:
            groups.setdefault((ErrorKind.MODEL, key), []).append(test)
    return [
        NewErrorGroup(
            kind=kind,
            key=key,
            tests=tuple(
                NewErrorGroupTest(
                    test_result_id=test.result_id,
                    test_case_id=test.test_case_id,
                    name=test.name,
                )
                for test in tests
            ),
        )
        for (kind, key), tests in sorted(
            groups.items(), key=lambda item: (-len(item[1]), item[0])
        )
    ]


def _model_key(message: str | None) -> str | None:
    first_line = next(
        (line for line in (message or "").splitlines() if line.strip()), None
    )
    if first_line is None or (match := _MODEL_RULE.match(first_line)) is None:
        return None
    return match["model"]
