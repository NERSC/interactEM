import asyncio
from typing import Any

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage
from interactem.core.nats.publish import publish_image
from interactem.operators.operator import AsyncOperator

logger = get_logger()


class ImageDisplay(AsyncOperator):
    def __init__(self):
        super().__init__()
        self._image_count = 0

        self.image_stream = None

    async def _publish_image(self, image_data: bytes):

        # We publish this on the canonical operator ID,
        # TODO: may need to adjust the way we are handling this
        # in the frontend to use the runtime ID instead
        await publish_image(
            self.js,
            image_data=image_data,
            canonical_operator_id=self.info.canonical_id,
        )

    async def kernel(
        self, inputs: BytesMessage | None, parameters: dict[str, Any]
    ) -> None:
        if not inputs:
            return

        image_data = inputs.data

        logger.info(
            f"Received image {self._image_count} data with length {len(image_data)}"
        )
        self._image_count += 1

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
