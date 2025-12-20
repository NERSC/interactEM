import inspect
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from interactem.core.config import cfg


class ISO8601Formatter(logging.Formatter):
    """Custom formatter that outputs timestamps in ISO 8601 format with timezone."""

    def formatTime(self, record, datefmt=None):
        return datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
            timespec="milliseconds"
        )


class StreamToLogger:
    """File-like stream object that redirects writes to a logger instance."""

    def __init__(self, logger: logging.Logger, log_level: int = logging.INFO):
        self.logger = logger
        self.log_level = log_level

    def write(self, buf: str) -> int:
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())
        return len(buf)

    def flush(self) -> None:
        pass


_logging_configured = False
_file_handler_added = False
_stdout_redirected = False


def get_logger(
    level: str = cfg.LOG_LEVEL.value, log_file: Path | None = None
) -> logging.Logger:
    """
    Get a logger for the calling module with ISO 8601 formatted timestamps.

    Args:
        level: Logging level (e.g., 'DEBUG', 'INFO', 'WARNING')
        log_file: Optional path to log file. Adds file handler if provided.

    Returns:
        Logger instance for the calling module.
    """
    global _logging_configured, _file_handler_added, _stdout_redirected

    root_logger = logging.getLogger()
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = ISO8601Formatter(log_format)

    # Configure root logger on first call
    if not _logging_configured:
        root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        console_handler = logging.StreamHandler(sys.stderr if log_file else sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # Suppress noisy third-party warnings
        logging.getLogger("nats.js.kv").setLevel(logging.ERROR)

        _logging_configured = True

    # Add file handler if requested
    if log_file and not _file_handler_added:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        _file_handler_added = True

    # Redirect stdout/stderr when file logging is enabled
    if _file_handler_added and not _stdout_redirected:
        sys.stdout = StreamToLogger(root_logger, logging.INFO)
        sys.stderr = StreamToLogger(root_logger, logging.ERROR)
        _stdout_redirected = True

    # Get caller's module name
    frame = inspect.currentframe()
    module = inspect.getmodule(frame.f_back) if frame else None
    module_name = (
        module.__name__ if module and module.__name__ != "__main__" else "__main__"
    )

    # Return logger for calling module
    logger = logging.getLogger(module_name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger
