import sys

from loguru import logger


def configure_logging(log_level: str = "INFO") -> None:
    """Configure loguru with consistent formatting across the application."""
    logger.remove()

    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>",
        level=log_level,
        colorize=True,
    )


__all__ = ["logger", "configure_logging"]
