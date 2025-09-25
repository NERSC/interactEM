import asyncio
import json
from typing import Any

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage
from interactem.core.nats import create_or_update_stream
from interactem.core.nats.config import TABLE_STREAM_CONFIG
from interactem.core.nats.publish import publish_table_data
from interactem.operators.operator import AsyncOperator

logger = get_logger()


class TableDisplay(AsyncOperator):
    """
    Expects a dictionary pickled DataFrame(s) and publishes them to a
    NATS stream.
    """

    def __init__(self):
        super().__init__()
        self.table_stream = None

    async def _ensure_stream(self):
        if not self.table_stream:
            logger.info(f"Ensuring NATS stream '{TABLE_STREAM_CONFIG.name}' exists...")
            self.table_stream = await create_or_update_stream(
                TABLE_STREAM_CONFIG, self.js
            )
            logger.info(f"NATS stream '{TABLE_STREAM_CONFIG.name}' ensured.")

    async def _publish_table_data(self, table_data_json: bytes):
        await self._ensure_stream()

        await publish_table_data(
            self.js,
            table_data_json=table_data_json,
            operator_id=self.info.canonical_id,
        )

    async def kernel(
        self, inputs: BytesMessage | None, parameters: dict[str, Any]
    ) -> None:
        if not inputs:
            logger.debug("No input message received.")
            return

        input_data = json.loads(inputs.data.decode("utf-8"))
        logger.debug("Successfully deserialized input data using JSON.")

        if not isinstance(input_data, dict):
            raise ValueError("Deserialized data is not a dictionary. Cannot process.")

        publishable_data: dict[str, Any] = {"tables": {}}

        for key, value in input_data.items():
            if isinstance(value, list):
                publishable_data["tables"][key] = value
                logger.debug(f"Using pre-serialized records for '{key}'.")
            else:
                logger.warning(
                    f"Data for key '{key}' is not a list. Skipping this entry."
                )
                return

        serialized_json_data = json.dumps(publishable_data).encode("utf-8")
        logger.debug(
            f"Serialized table data to JSON ({len(serialized_json_data)} bytes)."
        )

        await self._publish_table_data(serialized_json_data)


async def async_main():
    op = TableDisplay()
    await op.start()


def main():
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Shutting down table-display operator...")
    finally:
        print("TableDisplay application terminated.")


if __name__ == "__main__":
    main()
