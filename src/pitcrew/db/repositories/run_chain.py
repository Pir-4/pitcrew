from uuid import UUID

from sqlalchemy import select

from pitcrew.constants import Environment
from pitcrew.db.models.run import Run
from pitcrew.db.models.run_chain import RunChain
from pitcrew.db.repositories.base import BaseRepository
from pitcrew.db.repositories.exceptions import CouldNotCreateEntityException


class RunChainRepository(BaseRepository[RunChain]):
    """Loads and saves Run chains whole, with their Runs: lookups, get-or-create of a chain
    with its Nightly run, and one save. The chain's transitions are methods of `RunChain`."""

    def get_by_trace_id(self, trace_id: UUID) -> RunChain | None:
        """
        Args:
            trace_id: The trace id the chain's triggers were answered with.
        """
        return self._session.scalar(
            select(RunChain).where(RunChain.trace_id == trace_id)
        )

    def get_by_pipeline(self, pipeline_id: int) -> RunChain | None:
        """The Run chain one of whose Runs is the pipeline: a pipeline belongs to one Run.

        Args:
            pipeline_id: The pipeline of a Run of any kind.
        """
        return self._session.scalar(
            select(RunChain).join(Run).where(Run.pipeline_id == pipeline_id)
        )

    def get_or_create_for_nightly_run(
        self,
        *,
        team: str,
        environment: Environment,
        nightly_pipeline_id: int,
        nightly_launch_id: int,
    ) -> RunChain:
        """The Run chain the pipeline belongs to; a new one (`RunChain.for_nightly_run`) the
        first time. The caller checks that the pipeline is the chain's Nightly run: an
        existing chain may hold it as another kind of Run.

        Args:
            team: The Team of the Nightly run.
            environment: The Environment it ran on.
            nightly_pipeline_id: Its pipeline; a pipeline belongs to one Run.
            nightly_launch_id: Its Allure launch.
        """
        chain = self.get_by_pipeline(nightly_pipeline_id)
        if chain is not None:
            return chain
        try:
            return self.create(
                RunChain.for_nightly_run(
                    team=team,
                    environment=environment,
                    pipeline_id=nightly_pipeline_id,
                    launch_id=nightly_launch_id,
                )
            )
        except CouldNotCreateEntityException:
            # A concurrent trigger for the same Nightly run created it first.
            existing = self.get_by_pipeline(nightly_pipeline_id)
            if existing is None:
                raise
            return existing

    def get(self, chain_id: int) -> RunChain:
        """
        Args:
            chain_id: The Run chain.

        Raises:
            NoResultFound: There is no such Run chain.
        """
        return self._session.get_one(RunChain, chain_id)

    def save(self, chain: RunChain) -> None:
        """Commits the chain as it stands, with its Runs: called after every transition.

        Args:
            chain: A Run chain of this repository's session.
        """
        self._session.add(chain)
        self._session.commit()
