import asyncio
import os

from core.constants import OPERATOR_ID_ENV_VAR
from core.logger import get_logger
from operators.examples import recv_image, send_image_every_second

logger = get_logger("operator_main", "DEBUG")

OPERATOR_ID = os.getenv(OPERATOR_ID_ENV_VAR)


async def async_main():
    if OPERATOR_ID is None:
        logger.error("No operator ID provided")
        return

    # Initialize the operator with the provided ID
    if OPERATOR_ID == "12345678-1234-1234-1234-1234567890ab":
        operator = send_image_every_second()
    else:
        operator = recv_image()

    await operator.start()


def main():
    # Run the async main function using asyncio.run
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Shutting down operator...")
    finally:
        print("Application terminated.")


if __name__ == "__main__":
    main()
