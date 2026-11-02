from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pitcrew.db.migrate import migrate


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    """The sessions of a fresh SQLite file, migrated as the service migrates its DB."""
    engine = create_engine(f"sqlite:///{tmp_path / 'pitcrew.db'}")
    migrate(engine)
    yield sessionmaker(engine)
    engine.dispose()
