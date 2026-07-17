"""M1 static bearer authentication middleware."""

from hmac import compare_digest

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

from spine.problems import problem_response


class StaticBearerAuthMiddleware(BaseHTTPMiddleware):
    """Require the one static M1 bearer token on every HTTP route."""

    def __init__(self, app: ASGIApp, *, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        authorization = request.headers.get("Authorization", "")
        scheme, separator, credential = authorization.partition(" ")
        valid = (
            separator == " "
            and scheme.lower() == "bearer"
            and bool(credential)
            and compare_digest(credential, self._token)
        )
        if not valid:
            return problem_response(
                status=401,
                title="Unauthorized",
                detail="A valid static bearer token is required.",
                instance=request.url.path,
                endpoint=f"{request.method} {request.url.path}",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)
