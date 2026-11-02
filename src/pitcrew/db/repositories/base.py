from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from pitcrew.db.models.base import Base
from pitcrew.db.repositories.exceptions import CouldNotCreateEntityException


class BaseRepository[ModelT: Base]:
    """Access to one table. Methods are added when a caller needs them, not in advance."""

    def __init__(self, session: Session) -> None:
        """
        Args:
            session: The session of the `Repositories` that created the repository.
        """
        self._session = session

    def create(self, entity: ModelT) -> ModelT:
        """Inserts and commits the entity; a failed insert is rolled back.

        Args:
            entity: The new row.

        Raises:
            CouldNotCreateEntityException: The insert failed, e.g. on a unique constraint.
        """
        self._session.add(entity)
        try:
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise CouldNotCreateEntityException(
                f"Could not create {type(entity).__name__}"
            ) from error
        return entity
