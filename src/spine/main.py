"""FastAPI application factory for the M1 spine scaffold."""

from http import HTTPStatus

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from spine.auth import StaticBearerAuthMiddleware
from spine.config import Settings
from spine.inject.router import router as inject_router
from spine.memory.router import router as memory_router
from spine.problems import ProblemJSONResponse, problem_openapi, problem_response


class HealthResponse(BaseModel):
    ok: bool
    version: str


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the service app; production calls this as a Uvicorn factory."""

    resolved = settings or Settings()  # type: ignore[call-arg]
    bearer_contract = HTTPBearer(auto_error=False, scheme_name="StaticBearer")
    app = FastAPI(
        title="N8 Spine",
        version=resolved.version,
        dependencies=[Depends(bearer_contract)],
    )
    app.state.settings = resolved
    app.add_middleware(
        StaticBearerAuthMiddleware,
        token=resolved.token.get_secret_value(),
    )

    @app.exception_handler(RequestValidationError)
    async def validation_problem(
        request: Request,
        exc: RequestValidationError,
    ) -> ProblemJSONResponse:
        return problem_response(
            status=422,
            title="Unprocessable Content",
            detail="The request does not match the endpoint contract.",
            instance=request.url.path,
            endpoint=f"{request.method} {request.url.path}",
            extensions={"errors": jsonable_encoder(exc.errors())},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_problem(request: Request, exc: StarletteHTTPException) -> ProblemJSONResponse:
        try:
            title = HTTPStatus(exc.status_code).phrase
        except ValueError:
            title = "HTTP Error"
        detail = exc.detail if isinstance(exc.detail, str) else title
        return problem_response(
            status=exc.status_code,
            title=title,
            detail=detail,
            instance=request.url.path,
            endpoint=f"{request.method} {request.url.path}",
            headers=exc.headers,
        )

    @app.get(
        "/healthz",
        response_model=HealthResponse,
        responses={401: problem_openapi("Bearer token missing or invalid")},
    )
    async def healthz() -> HealthResponse:
        return HealthResponse(ok=True, version=resolved.version)

    app.include_router(inject_router)
    app.include_router(memory_router)
    return app
