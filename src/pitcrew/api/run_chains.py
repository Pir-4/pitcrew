from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from pitcrew.api.auth import require_trigger_token
from pitcrew.api.dependencies import get_repositories
from pitcrew.api.schemas import RunChainResponse
from pitcrew.db.repositories.container import Repositories
from pitcrew.log import bind_log_context

router = APIRouter()


@router.get(
    "/run-chains/{trace_id}",
    dependencies=[Depends(require_trigger_token)],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or wrong bearer token"},
        status.HTTP_404_NOT_FOUND: {"description": "No Run chain with this trace id"},
    },
)
def get_run_chain(
    trace_id: UUID,
    db: Annotated[Repositories, Depends(get_repositories)],
) -> RunChainResponse:
    """The Run chain with the trace id its triggers were answered with: the Step running now
    and what it is doing, its Runs in the order they were started, its Error groups and its
    Conclusion."""
    bind_log_context(trace_id=str(trace_id))
    chain = db.run_chains.get_by_trace_id(trace_id)
    if chain is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"No Run chain with trace id {trace_id}"
        )
    return RunChainResponse.from_chain(chain, db.error_groups.for_chain(chain.id))
