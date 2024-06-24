import argparse

import numpy as np

from zmglue.logger import get_logger
from zmglue.models.messages import BaseMessage, DataMessage
from zmglue.operator import Operator

logger = get_logger("operator0", "DEBUG")


def main():
    parser = argparse.ArgumentParser(
        description="Initialize an Operator with a specific ID."
    )
    parser.add_argument(
        "--id", type=str, required=True, help="The ID of the Operator to initialize."
    )

    args = parser.parse_args()

    operator_id = args.id
    operator = Operator(id=operator_id)

    def dummy(message: BaseMessage) -> BaseMessage:
        return message

    operator.set_processing_function(dummy)

    logger.info(f"Initializing Operator with ID {operator_id}...")
    operator.start()


if __name__ == "__main__":
    main()
