class RepositoryException(Exception):
    """Base of the repository errors; callers catch these, not the SQLAlchemy ones."""


class CouldNotCreateEntityException(RepositoryException):
    pass
