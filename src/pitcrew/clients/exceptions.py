class ClientException(Exception):
    """An error answer of a service: its own reason and the request it answered,
    `<reason> (<METHOD> <url>)`. Raised as is for an error status no caller tells apart; the
    subclasses are the ones a caller may.

    A client whose URL holds a secret (a Slack webhook) masks it through
    `BaseClient._error_url` before it gets here.
    """

    def __init__(self, reason: str, method: str, url: str) -> None:
        """
        Args:
            reason: The service's own reason for the error answer.
            method: The HTTP method of the request.
            url: The URL of the request, masked when it holds a secret.
        """
        super().__init__(f"{reason} ({method} {url})")
        self.reason = reason
        self.method = method
        self.url = url


class UnauthorizedException(ClientException):
    """`401`: the service rejected Pitcrew's own token, a problem of the service config, not
    of what the call asked for."""


class AccessDeniedException(ClientException):
    """`403`: the token may not see the resource. TestOps answers so also for a resource that
    does not exist."""


class NotFoundException(ClientException):
    """`404`: the resource does not exist."""
