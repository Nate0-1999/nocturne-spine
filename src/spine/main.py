"""FastAPI application factory for the M1 spine service."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException

from spine.auth import StaticBearerAuthMiddleware
from spine.config import Settings
from spine.db.engine import make_engine
from spine.db.session import make_session_factory
from spine.embeddings import EmbeddingProvider, OpenAIEmbeddingProvider
from spine.inject.decisions import DecisionService
from spine.inject.router import router as inject_router
from spine.inject.service import PrepareService
from spine.memory.router import router as memory_router
from spine.memory.service import MemoryService
from spine.problems import ProblemJSONResponse, problem_openapi, problem_response

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    ok: bool
    version: str


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> FastAPI:
    """Create the service app; production calls this as a Uvicorn factory."""

    resolved = settings or Settings()  # type: ignore[call-arg]
    owned_engine = None
    if session_factory is None:
        owned_engine = make_engine(resolved.database_url)
        session_factory = make_session_factory(owned_engine)

    owned_provider = None
    if embedding_provider is None:
        configured_key = (
            resolved.openai_api_key.get_secret_value() if resolved.openai_api_key else None
        )
        owned_provider = OpenAIEmbeddingProvider(
            api_key=configured_key or None,
            model=resolved.embed_model,
            dimensions=resolved.embed_dim,
        )
        embedding_provider = owned_provider

    memory_service = MemoryService(
        session_factory,
        embedding_provider,
        dedup_dup=resolved.dedup_dup,
        dedup_sim=resolved.dedup_sim,
        label_max=resolved.label_max,
        memory_max_tokens=resolved.memory_max_tokens,
    )
    prepare_service = PrepareService(session_factory, embedding_provider)
    decision_service = DecisionService(session_factory)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if owned_provider is not None:
                await owned_provider.aclose()
            if owned_engine is not None:
                await owned_engine.dispose()

    bearer_contract = HTTPBearer(auto_error=False, scheme_name="StaticBearer")
    app = FastAPI(
        title="N8 Spine",
        version=resolved.version,
        dependencies=[Depends(bearer_contract)],
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.memory_service = memory_service
    app.state.prepare_service = prepare_service
    app.state.decision_service = decision_service
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

    @app.exception_handler(Exception)
    async def unexpected_problem(request: Request, exc: Exception) -> ProblemJSONResponse:
        logger.error(
            "Unhandled Spine request failure",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return problem_response(
            status=500,
            title="Internal Server Error",
            detail="The request could not be completed.",
            instance=request.url.path,
            endpoint=f"{request.method} {request.url.path}",
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
