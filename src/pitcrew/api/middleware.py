import logging
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from pitcrew.log import Stopwatch, get_logger, log_scope

logger = get_logger(__name__)

# Polled by the cluster's probes: a line per call would bury the rest.
QUIET_PATHS = frozenset({"/health"})

REQUEST_ID_HEADER = b"x-request-id"


class RequestLogMiddleware:
    """One log line per HTTP request, in place of uvicorn's access log: method, path, status
    and duration, plus what the request bound to its log scope (the trace id of its Run
    chain, the trigger). Every line written while serving it carries its `request_id`, also
    sent back as `X-Request-Id`. A request that raised is logged here with the error and its
    context."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in QUIET_PATHS:
            await self.app(scope, receive, send)
            return
        request_id = str(uuid4())
        stopwatch = Stopwatch()
        fields = {"method": scope["method"], "path": scope["path"]}

        async def send_logged(message: Message) -> None:
            if message["type"] == "http.response.start":
                fields["status_code"] = message["status"]
                message["headers"] = [
                    *message.get("headers", []),
                    (REQUEST_ID_HEADER, request_id.encode()),
                ]
            elif message["type"] == "http.response.body" and not message.get(
                "more_body"
            ):
                # Logged once the answer is sent, before the background tasks run.
                status_code = fields["status_code"]
                level = logging.INFO if status_code < 400 else logging.WARNING
                if status_code >= 500:
                    level = logging.ERROR
                logger.log(level, "Request handled", **fields, duration_ms=stopwatch.ms)
            await send(message)

        with log_scope(request_id=request_id):
            try:
                await self.app(scope, receive, send_logged)
            except Exception:
                logger.exception("Request failed", **fields, duration_ms=stopwatch.ms)
                raise
