import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from pitcrew.constants import Environment
from pitcrew.db.models import RunChain
from pitcrew.db.models.post import PostKind
from pitcrew.db.repositories.container import Repositories


def test_store_refuses_a_second_post_of_the_same_chain_kind_and_key(
    session_factory: sessionmaker[Session],
) -> None:
    chain = RunChain.for_nightly_run(
        team="Gateway",
        environment=Environment.STAGING,
        pipeline_id=478951,
        launch_id=276357,
    )
    chain.record_post(PostKind.CONCLUSION)
    chain.record_post(PostKind.CONCLUSION)

    with Repositories(session_factory) as db, pytest.raises(IntegrityError):
        db.run_chains.save(chain)
