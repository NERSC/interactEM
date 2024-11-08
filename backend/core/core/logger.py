import inspect
import logging

import coloredlogs

from core.config import cfg


def get_logger(level: str = cfg.LOG_LEVEL.value) -> logging.Logger:
    """
    Creates and returns a logger with pretty-printed, colored logs.

    Parameters:
    - level: The logging level as a string (e.g., 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').

    Returns:
    - A logging.Logger instance with colored output configured.
    """
    # Determine the name of the module from which get_logger is called
    frame = inspect.currentframe()
    caller_frame = frame.f_back if frame else None
    module_name = "__main__"

    if caller_frame:
        # Get the module name from the caller's frame
        module = inspect.getmodule(caller_frame)
        if module and module.__name__ != "__main__":
            module_name = module.__name__

    # Create a logger instance with the module name
    logger = logging.getLogger(module_name)

    # Set the logging level based on the provided level string
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")
    logger.setLevel(numeric_level)

    # Define the coloredlogs format and field styles
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    field_styles = {
        "asctime": {"color": "green"},
        "hostname": {"color": "magenta"},
        "levelname": {"color": "white", "bold": True},
        "name": {"color": "blue"},
        "programname": {"color": "cyan"},
    }

    # Apply the coloredlogs setup to the logger
    coloredlogs.install(
        level=numeric_level, fmt=log_format, field_styles=field_styles, logger=logger
    )

    return logger
