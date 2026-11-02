import pytest
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session, sessionmaker

from pitcrew.constants import Environment
from pitcrew.db.models import RunChain
from pitcrew.db.repositories.container import Repositories


def test_store_refuses_a_status_none_of_its_enum_values(
    session_factory: sessionmaker[Session],
) -> None:
    chain = RunChain.for_nightly_run(
        team="Gateway",
        environment=Environment.STAGING,
        pipeline_id=478951,
        launch_id=276357,
    )
    chain.nightly_run.outcome = "flaky"  # ty: ignore[invalid-assignment]

    with Repositories(session_factory) as db, pytest.raises(StatementError):
        db.run_chains.save(chain)
