"""Where an exception an endpoint lets through becomes its HTTP answer.

`main` registers `EXCEPTION_HANDLERS` on the app; an endpoint holds no `try` / `except` for
these exceptions. Each answer is `{"detail": <reason>}`, the body of FastAPI's own errors.
"""

from collections.abc import Awaitable, Callable

from fastapi import Request, status
from fastapi.responses import JSONResponse

from pitcrew.clients.exceptions import UnauthorizedException
from pitcrew.config.team import UnknownTeamException
from pitcrew.log import get_logger
from pitcrew.steps.exceptions import StepException, StepNotImplementedException

logger = get_logger(__name__)


def _answer(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status_code)


async def _unknown_team(request: Request, error: UnknownTeamException) -> JSONResponse:
    return _answer(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error))


async def _step_not_implemented(
    request: Request, error: StepNotImplementedException
) -> JSONResponse:
    return _answer(status.HTTP_501_NOT_IMPLEMENTED, str(error))


async def _trigger_rejected(request: Request, error: StepException) -> JSONResponse:
    logger.warning("Trigger rejected", reason=error.reason, **error.details)
    return _answer(status.HTTP_422_UNPROCESSABLE_CONTENT, error.reason)


async def _testops_rejected_token(
    request: Request, error: UnauthorizedException
) -> JSONResponse:
    # Pitcrew's own token, not the caller's mistake: a bad gateway, not a 4xx.
    logger.error("TestOps rejected Pitcrew's token", error=str(error))
    return _answer(
        status.HTTP_502_BAD_GATEWAY,
        f"TestOps rejected Pitcrew's token (ALLURE_TOKEN): {error}",
    )


EXCEPTION_HANDLERS: dict[type[Exception], Callable[..., Awaitable[JSONResponse]]] = {
    UnknownTeamException: _unknown_team,
    StepNotImplementedException: _step_not_implemented,
    StepException: _trigger_rejected,
    UnauthorizedException: _testops_rejected_token,
}
"""Exception → its handler. A handler answers for its class and every subclass."""
