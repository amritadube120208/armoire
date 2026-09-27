import logging
import sys
from app.core.config import settings

try:
    import structlog

    def setup_logging():
        shared_processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ]

        if settings.ENVIRONMENT == "development":
            processors = shared_processors + [structlog.dev.ConsoleRenderer()]
        else:
            processors = shared_processors + [structlog.processors.JSONRenderer()]

        structlog.configure(
            processors=processors,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=logging.DEBUG if settings.DEBUG else logging.INFO,
        )

    def get_logger(name: str):
        return structlog.get_logger(name)

except ImportError:
    def setup_logging():
        logging.basicConfig(
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stdout,
            level=logging.DEBUG if settings.DEBUG else logging.INFO,
        )

    def get_logger(name: str):
        return logging.getLogger(name)
