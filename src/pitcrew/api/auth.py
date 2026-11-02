import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pitcrew.config.settings import Settings, get_settings


def require_trigger_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Lets through only callers that hold `PITCREW_TRIGGER_TOKEN`, compared in constant time."""
    expected = settings.trigger_token.get_secret_value().encode()
    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode(), expected
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
