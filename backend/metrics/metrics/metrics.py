import asyncio
from collections import deque

import nats
import nats.js
import nats.js.errors
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext
from nats.js.errors import KeyNotFoundError, NoKeysError
from nats.js.kv import KeyValue

from core.constants import BUCKET_METRICS, BUCKET_METRICS_TTL
from core.logger import get_logger
from core.models.ports import PortMetrics
from core.nats import create_bucket_if_doesnt_exist

from .config import cfg

logger = get_logger("orchestrator", "DEBUG")


class MovingAverage:
    def __init__(self, max_seconds: int):
        self.max_seconds = max_seconds
        self.values: deque[tuple[float, float]] = deque()

    def add_value(self, time: float, value: float):
        self.values.append((time, value))
        self._remove_old_values(time)

    def _remove_old_values(self, current_time: float):
        while self.values and (current_time - self.values[0][0]) > self.max_seconds:
            self.values.popleft()

    def average(self) -> float:
        if not self.values:
            return 0.0
        total_bytes = self.values[-1][1] - self.values[0][1]
        total_time = self.values[-1][0] - self.values[0][0]
        return (total_bytes * 8) / (total_time * 1_000_000) if total_time > 0 else 0.0


async def metrics_watch(bucket: KeyValue):
    moving_averages: dict[str, dict[str, dict[str, MovingAverage]]] = {}

    while True:
        keys: list[str] = []
        try:
            keys = await bucket.keys()
        except NoKeysError:
            await asyncio.sleep(1)
            continue

        current_time = asyncio.get_event_loop().time()

        for key in keys:
            try:
                entry = await bucket.get(key)
            except KeyNotFoundError:
                continue
            if not entry.value:
                continue
            metrics = PortMetrics.model_validate_json(entry.value)

            if key not in moving_averages:
                moving_averages[key] = {
                    "send": {
                        "2s": MovingAverage(2),
                        "5s": MovingAverage(5),
                        "30s": MovingAverage(30),
                    },
                    "recv": {
                        "2s": MovingAverage(2),
                        "5s": MovingAverage(5),
                        "30s": MovingAverage(30),
                    },
                }

            moving_averages[key]["send"]["2s"].add_value(
                current_time, metrics.send_bytes
            )
            moving_averages[key]["send"]["5s"].add_value(
                current_time, metrics.send_bytes
            )
            moving_averages[key]["send"]["30s"].add_value(
                current_time, metrics.send_bytes
            )

            moving_averages[key]["recv"]["2s"].add_value(
                current_time, metrics.recv_bytes
            )
            moving_averages[key]["recv"]["5s"].add_value(
                current_time, metrics.recv_bytes
            )
            moving_averages[key]["recv"]["30s"].add_value(
                current_time, metrics.recv_bytes
            )

            if key == keys[0]:
                logger.info(f"Key: {key}")
                logger.info(
                    f"  Send 2s avg throughput: {moving_averages[key]['send']['2s'].average():.2f} Mbit/s"
                )
                logger.info(
                    f"  Send 5s avg throughput: {moving_averages[key]['send']['5s'].average():.2f} Mbit/s"
                )
                logger.info(
                    f"  Send 30s avg throughput: {moving_averages[key]['send']['30s'].average():.2f} Mbit/s"
                )
                logger.info(
                    f"  Recv 2s avg throughput: {moving_averages[key]['recv']['2s'].average():.2f} Mbit/s"
                )
                logger.info(
                    f"  Recv 5s avg throughput: {moving_averages[key]['recv']['5s'].average():.2f} Mbit/s"
                )
                logger.info(
                    f"  Recv 30s avg throughput: {moving_averages[key]['recv']['30s'].average():.2f} Mbit/s"
                )
        await asyncio.sleep(1)


async def main():
    nc: NATSClient = await nats.connect(servers=[str(cfg.NATS_SERVER_URL)])
    js: JetStreamContext = nc.jetstream()

    logger.info("Metrics microservice is running...")

    metrics_bucket = await create_bucket_if_doesnt_exist(
        js, BUCKET_METRICS, BUCKET_METRICS_TTL
    )

    await metrics_watch(metrics_bucket)


if __name__ == "__main__":
    asyncio.run(main())
