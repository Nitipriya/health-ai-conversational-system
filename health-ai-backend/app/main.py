from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.middleware import register_middleware
from app.core.rate_limiter import limiter
from app.db.session import engine

setup_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on startup and shutdown."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Primary AI provider: {settings.primary_ai_provider}")
    yield
    # Shutdown — close DB connection pool cleanly
    await engine.dispose()
    logger.info("Server shut down cleanly")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Health AI Conversational System API",
    docs_url="/docs",        # Swagger UI at /docs
    redoc_url="/redoc",      # ReDoc at /redoc
    lifespan=lifespan,
)

# ── Attach rate limiter ────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Register middleware ────────────────────────────────────────────────────────
register_middleware(app)

# ── Register all routes ───────────────────────────────────────────────────────
app.include_router(api_router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
async def health_check():
    """Quick endpoint to confirm the server is running."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }
