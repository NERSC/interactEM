import argparse
import asyncio
from uuid import UUID

from core.logger import get_logger
from operators.examples import create_hello_world, receive_hello_world

logger = get_logger("operator_main", "DEBUG")


async def async_main(operator_id: str):
    # Initialize the operator with the provided ID
    if operator_id == "12345678-1234-1234-1234-1234567890ab":
        operator = create_hello_world(UUID(operator_id))
    else:
        operator = receive_hello_world(UUID(operator_id))

    print(operator.id)

    await operator.start()


def main():
    parser = argparse.ArgumentParser(
        description="Initialize an Operator with a specific ID."
    )
    parser.add_argument(
        "--id", type=str, required=True, help="The ID of the Operator to initialize."
    )

    args = parser.parse_args()

    # Run the async main function using asyncio.run
    try:
        asyncio.run(async_main(args.id))
    except KeyboardInterrupt:
        logger.info("Shutting down operator...")
    finally:
        print("Application terminated.")


if __name__ == "__main__":
    main()
