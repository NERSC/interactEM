import logging

import coloredlogs


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Creates and returns a logger with pretty-printed, colored logs.

    Parameters:
    - name: Name of the logger, typically __name__ when used within a module.
    - level: The logging level as a string (e.g., 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').

    Returns:
    - A logging.Logger instance with colored output configured.
    """

    # Create a logger instance
    logger = logging.getLogger(name)

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
