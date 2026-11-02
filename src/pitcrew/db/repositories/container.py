from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session, sessionmaker

from pitcrew.db.repositories.error_group import ErrorGroupRepository
from pitcrew.db.repositories.error_group_test import ErrorGroupTestRepository
from pitcrew.db.repositories.run_chain import RunChainRepository
from pitcrew.db.services.error_group import ErrorGroupService


class Repositories:
    """The repositories of the service DB over one session, opened and closed by `with`:

    with Repositories(session_factory) as db:
        chain = db.run_chains.get_by_trace_id(trace_id)
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """
        Args:
            session_factory: Opens the session on `with`.
        """
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    @property
    def run_chains(self) -> RunChainRepository:
        return RunChainRepository(self._get_session())

    @property
    def error_groups(self) -> ErrorGroupRepository:
        return ErrorGroupRepository(self._get_session())

    @property
    def error_group_tests(self) -> ErrorGroupTestRepository:
        return ErrorGroupTestRepository(self._get_session())

    @property
    def error_group_service(self) -> ErrorGroupService:
        return ErrorGroupService(self._get_session())

    def _get_session(self) -> Session:
        if self._session is None:
            raise RuntimeError(
                f"No active session. Use {type(self).__name__} as a context manager."
            )
        return self._session
