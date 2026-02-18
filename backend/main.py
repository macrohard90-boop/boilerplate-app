"""FastAPI application factory."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response

from backend.core.config import settings
from backend.core.redis import close_redis, redis_health_check
from backend.core.database import close_db, db_health_check, get_db
from backend.core.module_loader import load_modules

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting %s (%s)", settings.app_name, settings.app_env)

    # Load modules
    loaded = load_modules(app)
    app.state.loaded_modules = loaded

    # Start background tasks
    tasks: list[asyncio.Task] = []
    if settings.enable_payments:
        from modules.payments.services.order_reaper import reaper_loop

        tasks.append(asyncio.create_task(reaper_loop()))
        logger.info("Order reaper background task started")

    yield

    # Cancel background tasks
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    # Cleanup
    await close_redis()
    await close_db()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.app_name,
        docs_url="/api/docs" if settings.debug else None,
        redoc_url="/api/redoc" if settings.debug else None,
        openapi_url="/api/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # Tracking middleware (non-blocking, fire-and-forget)
    if settings.enable_tracking:
        from modules.tracking.services.tracking_middleware import TrackingMiddleware
        app.add_middleware(TrackingMiddleware)

    # Rate limiting
    from backend.core.middleware import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)

    # CORS
    origins = [settings.frontend_url]
    if settings.app_env == "development":
        origins.append("http://localhost:3000")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health endpoints
    @app.get("/api/health")
    async def health():
        redis_status = await redis_health_check()
        db_status = await db_health_check()
        return {
            "status": "ok",
            "services": {
                "redis": redis_status.get("status", "error"),
                "db": db_status.get("status", "error"),
            },
        }

    @app.get("/api/health/redis")
    async def health_redis():
        return await redis_health_check()

    @app.get("/api/health/db")
    async def health_db():
        return await db_health_check()

    # SEO root-level routes (sitemap.xml, robots.txt)
    from sqlalchemy.ext.asyncio import AsyncSession

    @app.get("/sitemap.xml", response_class=Response)
    async def sitemap_xml(db: AsyncSession = Depends(get_db)):
        from modules.seo.services.sitemap_service import generate_sitemap

        xml = await generate_sitemap(db)
        return Response(content=xml, media_type="application/xml")

    @app.get("/robots.txt", response_class=PlainTextResponse)
    async def robots_txt():
        from modules.seo.services.robots_service import generate_robots

        return PlainTextResponse(content=generate_robots())

    return app


app = create_app()
