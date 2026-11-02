"""Work across `error_groups` and `error_group_tests`."""

from collections.abc import Sequence

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from pitcrew.db.models.error_group import ErrorGroup, ErrorGroupTest, NewErrorGroup
from pitcrew.db.repositories.error_group import ErrorGroupRepository
from pitcrew.db.repositories.error_group_test import ErrorGroupTestRepository
from pitcrew.db.repositories.exceptions import CouldNotCreateEntityException


class ErrorGroupService:
    """Stores the Error groups of a Run chain with their tests, in one commit."""

    def __init__(self, session: Session) -> None:
        """
        Args:
            session: The session of the `Repositories` that created the service.
        """
        self._session = session
        self._groups = ErrorGroupRepository(session)
        self._tests = ErrorGroupTestRepository(session)

    def record_for_chain(
        self, chain_id: int, groups: Sequence[NewErrorGroup]
    ) -> list[ErrorGroup]:
        """Stores the Error groups of a Run chain with their tests in one commit, so that no
        group is ever stored without its tests, and answers the ones the chain has. A chain
        that has them already keeps them: a resumed Step does not record them twice.

        Args:
            chain_id: The Run chain.
            groups: The Error groups recognized among its Failed tests.

        Returns:
            The Error groups the chain has, stored.

        Raises:
            CouldNotCreateEntityException: The groups could not be stored; nothing was.
        """
        if self._groups.exists_for_chain(chain_id):
            return self._groups.for_chain(chain_id)
        try:
            for new_group in groups:
                group = self._groups.add(chain_id, new_group.kind, new_group.key)
                self._tests.add_for_group(
                    group.id,
                    (
                        ErrorGroupTest(
                            test_result_id=test.test_result_id,
                            test_case_id=test.test_case_id,
                            name=test.name,
                        )
                        for test in new_group.tests
                    ),
                )
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise CouldNotCreateEntityException(
                f"Could not create the Error groups of Run chain {chain_id}"
            ) from error
        return self._groups.for_chain(chain_id)
