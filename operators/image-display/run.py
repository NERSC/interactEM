import asyncio
from typing import Any

from core.constants import STREAM_IMAGES
from core.logger import get_logger
from core.models.messages import BytesMessage
from core.nats import create_or_update_stream
from core.nats.config import IMAGES_STREAM_CONFIG
from operators.operator import AsyncOperator

logger = get_logger()


class ImageDisplay(AsyncOperator):
    def __init__(self):
        super().__init__()

        self.image_stream = None

    # TODO Would be nice to be able todo this is a custom
    # start method, but that is currently not possible as
    # the start method doesn't return.
    async def _ensure_stream(self):
        if not self.image_stream:
            self.image_stream = await create_or_update_stream(
                IMAGES_STREAM_CONFIG, self.js
            )

    async def _publish_image(self, image_data: bytes):
        await self._ensure_stream()

        await self.js.publish(
            subject=f"{STREAM_IMAGES}.{self.id}",
            payload=image_data,
        )

    async def kernel(
        self, inputs: BytesMessage | None, parameters: dict[str, Any]
    ) -> None:
        if not inputs:
            return

        image_data = inputs.data

        logger.info(f"Received image data with length {len(image_data)}")

        # Publish the image to the frontend
        await self._publish_image(image_data)


async def async_main():
    op = ImageDisplay()
    await op.start()


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
