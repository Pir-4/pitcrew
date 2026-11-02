from collections.abc import Iterable

from pitcrew.db.models.error_group import ErrorGroupTest
from pitcrew.db.repositories.base import BaseRepository


class ErrorGroupTestRepository(BaseRepository[ErrorGroupTest]):
    """Everything the service writes in the `error_group_tests` table; the tests of a group
    are read through `ErrorGroup.tests`."""

    def add_for_group(self, group_id: int, tests: Iterable[ErrorGroupTest]) -> None:
        """Adds the tests of an Error group; the caller commits, together with the group.

        Args:
            group_id: The Error group.
            tests: Its tests, not stored yet.
        """
        for test in tests:
            test.error_group_id = group_id
            self._session.add(test)
