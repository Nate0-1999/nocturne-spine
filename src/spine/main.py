"""FastAPI application factory for the Spine service."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException

from spine import __version__
from spine.auth import StaticBearerAuthMiddleware
from spine.config import Settings
from spine.db.engine import make_engine
from spine.db.migrate import packaged_head
from spine.db.session import make_session_factory
from spine.embeddings import EmbeddingProvider, OpenAIEmbeddingProvider
from spine.inject.decisions import DecisionService
from spine.inject.router import router as inject_router
from spine.inject.service import PrepareService
from spine.learner.router import router as learner_router
from spine.learner.scheduler import LearnerScheduler
from spine.learner.service import LearnerService, LearnerSettings
from spine.m2k.router import router as m2k_router
from spine.m2k.service import M2KService
from spine.memory.router import router as memory_router
from spine.memory.service import MemoryService
from spine.problems import ProblemJSONResponse, problem_openapi, problem_response
from spine.queue.router import router as queue_router
from spine.queue.service import QueueService
from spine.spend.reconciliation import (
    OpenRouterUsageClient,
    ReconciliationScheduler,
    ReconciliationService,
)
from spine.spend.router import router as spend_router
from spine.spend.service import SpendService
from spine.spend.views import SpendViewRefresher
from spine.vitals.router import router as vitals_router
from spine.vitals.service import VitalsService

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    ok: bool
    version: str
    schema_version: str | None


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

    spend_service = SpendService(session_factory)
    configured_key = resolved.openai_api_key.get_secret_value() if resolved.openai_api_key else None
    reconciliation_configured = bool(
        configured_key and urlparse(resolved.embed_base_url).hostname == "openrouter.ai"
    )
    vitals_service = VitalsService(
        session_factory,
        reconciliation_configured=reconciliation_configured,
    )

    owned_provider = None
    if embedding_provider is None:
        owned_provider = OpenAIEmbeddingProvider(
            api_key=configured_key or None,
            model=resolved.embed_model,
            dimensions=resolved.embed_dim,
            base_url=resolved.embed_base_url,
            receipt_sink=spend_service,
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
    queue_service = QueueService(session_factory, memory_service)
    prepare_service = PrepareService(session_factory, embedding_provider)
    decision_service = DecisionService(session_factory)
    spend_view_refresher = SpendViewRefresher(
        session_factory,
        interval_seconds=resolved.spend_view_refresh_seconds,
    )
    reconciliation_client = (
        OpenRouterUsageClient(api_key=configured_key or "", base_url=resolved.embed_base_url)
        if reconciliation_configured
        else None
    )
    reconciliation_service = (
        ReconciliationService(
            session_factory,
            reconciliation_client,
            tolerance_usd=resolved.reconciliation_tolerance_usd,
        )
        if reconciliation_client is not None
        else None
    )
    reconciliation_scheduler = (
        ReconciliationScheduler(
            reconciliation_service,
            interval_seconds=resolved.reconciliation_hours * 3600,
        )
        if reconciliation_service is not None
        else None
    )
    learner_service = LearnerService(
        session_factory,
        settings=LearnerSettings(
            min_dispositions=resolved.learner_min_dispositions,
            holdout_fraction=resolved.learner_holdout_fraction,
            passive_discount=resolved.learner_passive_discount,
            pair_margin=resolved.learner_pair_margin,
            bias_l2=resolved.learner_bias_l2,
            win_margin=resolved.learner_win_margin,
        ),
    )
    m2k_service = M2KService(
        session_factory,
        graph_edge_sim=resolved.graph_edge_sim,
        holdout_fraction=resolved.learner_holdout_fraction,
        passive_discount=resolved.learner_passive_discount,
    )
    learner_scheduler = (
        None
        if resolved.learner_schedule_hours is None
        else LearnerScheduler(
            learner_service,
            interval_seconds=resolved.learner_schedule_hours * 3600,
        )
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if owned_engine is not None:
            spend_view_refresher.start()
            if reconciliation_scheduler is not None:
                reconciliation_scheduler.start()
            if learner_scheduler is not None:
                learner_scheduler.start()
        try:
            yield
        finally:
            if owned_engine is not None:
                if reconciliation_scheduler is not None:
                    await reconciliation_scheduler.stop()
                if learner_scheduler is not None:
                    await learner_scheduler.stop()
                await spend_view_refresher.stop()
            if owned_provider is not None:
                await owned_provider.aclose()
            if reconciliation_client is not None:
                await reconciliation_client.aclose()
            if owned_engine is not None:
                await owned_engine.dispose()

    bearer_contract = HTTPBearer(auto_error=False, scheme_name="StaticBearer")
    app = FastAPI(
        title="N8 Spine",
        version=__version__,
        dependencies=[Depends(bearer_contract)],
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.memory_service = memory_service
    app.state.queue_service = queue_service
    app.state.prepare_service = prepare_service
    app.state.decision_service = decision_service
    app.state.spend_service = spend_service
    app.state.spend_view_refresher = spend_view_refresher
    app.state.reconciliation_service = reconciliation_service
    app.state.reconciliation_scheduler = reconciliation_scheduler
    app.state.vitals_service = vitals_service
    app.state.learner_service = learner_service
    app.state.m2k_service = m2k_service
    app.state.learner_scheduler = learner_scheduler
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
        "/health",
        response_model=HealthResponse,
        responses={401: problem_openapi("Bearer token missing or invalid")},
        include_in_schema=False,
    )
    @app.get(
        "/healthz",
        response_model=HealthResponse,
        responses={401: problem_openapi("Bearer token missing or invalid")},
    )
    async def healthz() -> HealthResponse:
        return HealthResponse(ok=True, version=__version__, schema_version=packaged_head())

    app.include_router(inject_router)
    app.include_router(learner_router)
    app.include_router(m2k_router)
    app.include_router(memory_router)
    app.include_router(queue_router)
    app.include_router(spend_router)
    app.include_router(vitals_router)
    return app
