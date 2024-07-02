# zmglue/main.py

import argparse
from uuid import UUID

from zmglue.logger import get_logger
from zmglue.operators.examples import create_hello_world, receive_hello_world

logger = get_logger("operator_main", "DEBUG")


def main():
    parser = argparse.ArgumentParser(
        description="Initialize an Operator with a specific ID."
    )
    parser.add_argument(
        "--id", type=str, required=True, help="The ID of the Operator to initialize."
    )

    args = parser.parse_args()

    operator_id = args.id
    assert isinstance(operator_id, str)

    # Initialize the operator with the provided ID
    if operator_id == "12345678-1234-1234-1234-1234567890ab":
        operator = create_hello_world(UUID(operator_id))
    else:
        operator = receive_hello_world(UUID(operator_id))


if __name__ == "__main__":
    main()
