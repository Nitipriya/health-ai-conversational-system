import logging
import sys

from app.core.config import get_settings

settings = get_settings()


def setup_logging() -> None:
    """
    Call this once in main.py at startup.
    Sets up clean logging — DEBUG level in dev, INFO in prod.
    """
    log_level = logging.DEBUG if settings.debug else logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("groq").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger. Use this in every module instead of print().

    Usage:
        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
        logger.error("Something broke", exc_info=True)
    """
    return logging.getLogger(name)
