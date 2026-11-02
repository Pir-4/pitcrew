from pitcrew.constants import Environment
from pitcrew.db.models import RunChain


def test_rerun_launch_accepted_again_keeps_the_first() -> None:
    chain = RunChain.for_nightly_run(
        team="Gateway",
        environment=Environment.STAGING,
        pipeline_id=478951,
        launch_id=276357,
    )
    chain.start_rerun(pipeline_id=481658, test_case_count=223)
    chain.accept_rerun_launch(279328)

    chain.accept_rerun_launch(280791)

    assert chain.rerun is not None
    assert chain.rerun.launch_id == 279328
