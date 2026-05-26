import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


def register_middleware(app: FastAPI) -> None:
    """
    Register all middleware on the FastAPI app.
    Call this in main.py before starting the server.
    """

    # ── CORS ──────────────────────────────────────────────────────────────────
    # In development: allow all origins so your frontend (React/Next) can connect
    # In production: replace ["*"] with your actual frontend URL
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request logging ───────────────────────────────────────────────────────
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """
        Logs every request with:
        - A unique request ID (useful for tracing errors)
        - Method + path
        - Response status code
        - How long it took
        """
        request_id = str(uuid.uuid4())[:8]   # short ID e.g. "a3f9c1b2"
        start = time.perf_counter()

        logger.info(f"[{request_id}] → {request.method} {request.url.path}")

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000)
        logger.info(
            f"[{request_id}] ← {response.status_code} "
            f"({duration_ms}ms)"
        )

        # Attach request ID to response headers — handy for debugging
        response.headers["X-Request-ID"] = request_id
        return response
