from typing import Any

import httpx2 as httpx

from pitcrew.clients.exceptions import (
    AccessDeniedException,
    ClientException,
    NotFoundException,
    UnauthorizedException,
)
from pitcrew.log import Stopwatch, get_logger

logger = get_logger(__name__)

type Params = dict[str, str | int | list[str]]

TIMEOUT_SECONDS = 30

MAX_LOGGED_REASON_LENGTH = 500

EXCEPTIONS: dict[int, type[ClientException]] = {
    httpx.codes.UNAUTHORIZED: UnauthorizedException,
    httpx.codes.FORBIDDEN: AccessDeniedException,
    httpx.codes.NOT_FOUND: NotFoundException,
}


class BaseClient:
    """One HTTP connection pool to an external service, opened at startup and shared by the
    requests and the Steps. A client adds the calls Pitcrew needs on top of `_get`, `_post`
    and `_patch` (JSON answers) or `_send` (any answer); paths are relative to `base_url`."""

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str],
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Opens the connection pool.

        Args:
            base_url: The root of the service's API; request paths are relative to it.
            headers: Sent with every request, e.g. the service's auth token.
            transport: A faked transport serving recorded responses, for the tests.
        """
        self._http = httpx.Client(
            base_url=base_url,
            headers=headers,
            transport=transport,
            timeout=TIMEOUT_SECONDS,
        )

    def close(self) -> None:
        self._http.close()

    def _get(self, path: str, params: Params | None = None) -> Any:
        return self._request("GET", path, params=params)

    def _post(self, path: str, json: Any) -> Any:
        return self._request("POST", path, json=json)

    def _patch(self, path: str, json: Any) -> Any:
        return self._request("PATCH", path, json=json)

    def _request(
        self, method: str, path: str, params: Params | None = None, json: Any = None
    ) -> Any:
        """The JSON body of a successful response; an error one raises as `_send` does."""
        return self._send(method, path, params=params, json=json).json()

    def _send(
        self, method: str, path: str, params: Params | None = None, json: Any = None
    ) -> httpx.Response:
        """A successful response. `401`, `403` and `404` raise the exceptions of
        `EXCEPTIONS`, any other error status `ClientException`; each names the request by
        `_error_url`. Every call is logged: the request, the status and the duration, and the
        reason of an error answer."""
        stopwatch = Stopwatch()
        call = {"client": type(self).__name__, "method": method}
        try:
            response = self._http.request(method, path, params=params, json=json)
        except httpx.HTTPError as error:
            call["url"] = self._error_url(error.request)
            logger.warning(
                "External call failed",
                **call,
                error=str(error),
                duration_ms=stopwatch.ms,
            )
            raise
        call["url"] = self._error_url(response.request)
        if response.is_error:
            reason = self._error_message(response)
            logger.warning(
                "External call answered an error",
                **call,
                status_code=response.status_code,
                reason=reason[:MAX_LOGGED_REASON_LENGTH],
                duration_ms=stopwatch.ms,
            )
            exception = EXCEPTIONS.get(response.status_code, ClientException)
            raise exception(reason, method, call["url"])
        logger.info(
            "External call",
            **call,
            status_code=response.status_code,
            duration_ms=stopwatch.ms,
        )
        return response

    def _error_url(self, request: httpx.Request) -> str:
        """How an error and a log line name the URL of a request. A client whose URL holds a
        secret overrides this to mask it."""
        return str(request.url)

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        """The service's own reason for an error answer: `message` of a JSON body, else the
        body. A client of a service that puts it elsewhere overrides this."""
        try:
            return str(response.json()["message"])
        except (ValueError, KeyError, TypeError):
            return response.text
