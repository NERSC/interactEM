import anyio

from interactem.core.logger import get_logger
from interactem.orchestrator.app import app

logger = get_logger()


if __name__ == "__main__":
    try:
        anyio.run(app.run)
    except KeyboardInterrupt:
        logger.info("Orchestrator stopped by user")
    logger.info("Orchestrator process exited")
