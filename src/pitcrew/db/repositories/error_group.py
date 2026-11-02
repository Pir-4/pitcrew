from sqlalchemy import exists, select

from pitcrew.db.models.error_group import ErrorGroup, ErrorKind
from pitcrew.db.repositories.base import BaseRepository


class ErrorGroupRepository(BaseRepository[ErrorGroup]):
    """Everything the service reads and writes in the `error_groups` table."""

    def for_chain(self, chain_id: int) -> list[ErrorGroup]:
        """The Error groups of a Run chain with their tests, in the order they were recorded.

        Args:
            chain_id: The Run chain.
        """
        return list(
            self._session.scalars(
                select(ErrorGroup)
                .where(ErrorGroup.run_chain_id == chain_id)
                .order_by(ErrorGroup.id)
            )
        )

    def exists_for_chain(self, chain_id: int) -> bool:
        """Whether the Run chain has its Error groups stored.

        Args:
            chain_id: The Run chain.
        """
        return bool(
            self._session.scalar(
                select(exists().where(ErrorGroup.run_chain_id == chain_id))
            )
        )

    def add(self, chain_id: int, kind: ErrorKind, key: str) -> ErrorGroup:
        """Adds an Error group of a Run chain and gives it its id; the caller commits, together
        with the group's tests.

        Args:
            chain_id: The Run chain.
            kind: The Error kind.
            key: What broke, as the error names it.
        """
        group = ErrorGroup(run_chain_id=chain_id, kind=kind, key=key)
        self._session.add(group)
        self._session.flush()
        return group
