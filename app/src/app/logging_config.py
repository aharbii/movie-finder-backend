"""Logging bootstrap for the Movie Finder backend application.

Call ``configure_logging()`` once, as the very first statement in the
entry-point (``main.py``), before any other import creates a logger.

Environment variables
---------------------
LOG_LEVEL  : DEBUG | INFO | WARNING | ERROR | CRITICAL  (default: INFO)
LOG_FORMAT : text | json  (default: text)

Environment     Recommended settings
-----------     --------------------
local dev       LOG_LEVEL=DEBUG  LOG_FORMAT=text
CI              LOG_LEVEL=INFO   LOG_FORMAT=text
staging         LOG_LEVEL=INFO   LOG_FORMAT=json
production      LOG_LEVEL=WARNING  LOG_FORMAT=json

LangSmith handles AI-layer observability (tokens, model, tool calls, cost).
Python logging handles the application layer (HTTP, DB, orchestration, errors).
They are complementary — do not duplicate AI traces in Python logs.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime


class _JsonFormatter(logging.Formatter):
    """Formats log records as JSON for structured log ingestion (Azure Monitor)."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a log record to a single-line JSON string.

        Args:
            record: The log record to format.

        Returns:
            A JSON-encoded string representing the log entry.
        """
        data: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def configure_logging() -> None:
    """Bootstrap application logging from environment variables.

    Idempotent — safe to call multiple times; configuration is applied only once.

    Sets up a single ``StreamHandler`` (stdout) on each application namespace
    (``app``, ``chain``, ``imdbapi``, ``rag``) with ``propagate=False`` to
    prevent double-logging.  Third-party libraries are silenced below WARNING
    unless ``LOG_LEVEL=DEBUG`` is active.
    """
    # Idempotent guard — skip if already bootstrapped.
    if logging.getLogger("app").handlers:
        return

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get("LOG_FORMAT", "text").lower()
    level: int = getattr(logging, level_name, logging.INFO)

    if log_format == "json":
        formatter: logging.Formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    # Wire all application namespaces to the configured handler.
    for namespace in ("app", "chain", "imdbapi", "rag"):
        ns_logger = logging.getLogger(namespace)
        ns_logger.setLevel(level)
        ns_logger.addHandler(handler)
        ns_logger.propagate = False  # prevent double-logging via root

    # Suppress third-party noise below WARNING unless full DEBUG is active.
    _quiet_libs = ("httpx", "httpcore", "openai", "anthropic", "uvicorn.access")
    quiet_level = logging.DEBUG if level == logging.DEBUG else logging.WARNING
    for lib in _quiet_libs:
        logging.getLogger(lib).setLevel(quiet_level)

    # uvicorn.error stays at WARNING minimum even in DEBUG mode.
    logging.getLogger("uvicorn.error").setLevel(max(level, logging.WARNING))
