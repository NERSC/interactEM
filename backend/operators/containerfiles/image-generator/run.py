import asyncio
import os

from core.constants import OPERATOR_ID_ENV_VAR
from core.logger import get_logger
from operators.examples import send_image_every_second

logger = get_logger("operator_main", "DEBUG")

OPERATOR_ID = os.getenv(OPERATOR_ID_ENV_VAR)


async def async_main():
    if OPERATOR_ID is None:
        logger.error("No operator ID provided")
        return
    operator = send_image_every_second()
    await operator.start()


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Shutting down operator...")
    finally:
        print("Application terminated.")


if __name__ == "__main__":
    main()
