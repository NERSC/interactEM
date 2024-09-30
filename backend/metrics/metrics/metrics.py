import asyncio
from collections import deque
from enum import Enum

import nats
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext

from core.logger import get_logger
from core.models.operators import OperatorMetrics  # Import the OperatorMetrics model
from core.models.ports import PortMetrics
from core.nats import get_keys, get_metrics_bucket, get_val

from .config import cfg

logger = get_logger("metrics", "DEBUG")

class MetricType(str, Enum):
    THROUGHPUT = "throughput (Mbps)"
    MESSAGES = "messages"


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

    def average_throughput(self) -> float:
        if not self.values:
            return 0.0
        total_bytes = self.values[-1][1] - self.values[0][1]
        total_time = self.values[-1][0] - self.values[0][0]
        if total_time > 0:
            total_bits = total_bytes * 8
            total_megabits = total_bits / 1_000_000
            return total_megabits / total_time
        return 0.0

    def average_messages(self) -> float:
        if not self.values:
            return 0.0
        total_messages = self.values[-1][1] - self.values[0][1]
        total_time = self.values[-1][0] - self.values[0][0]
        return total_messages / total_time if total_time > 0 else 0.0

    def log_averages(self, interval: str, metric_type: MetricType, direction: str):
        metric_types = {
            MetricType.THROUGHPUT: self.average_throughput,
            MetricType.MESSAGES: self.average_messages,
        }
        avg = metric_types[metric_type]()
        logger.info(f"  {direction} {interval} avg {metric_type.value}: {avg:.2f}")



class PortMovingAverages:
    def __init__(self, intervals: list[int], update_interval: int):
        self.update_interval = update_interval
        self.send_bytes = {
            f"{interval}s": MovingAverage(interval) for interval in intervals
        }
        self.send_num_msgs = {
            f"{interval}s": MovingAverage(interval) for interval in intervals
        }
        self.recv_bytes = {
            f"{interval}s": MovingAverage(interval) for interval in intervals
        }
        self.recv_num_msgs = {
            f"{interval}s": MovingAverage(interval) for interval in intervals
        }

    def add_metrics(self, current_time: float, metric: PortMetrics):
        for moving_average in self.send_bytes.values():
            moving_average.add_value(current_time, metric.send_bytes)
        for moving_average in self.send_num_msgs.values():
            moving_average.add_value(current_time, metric.send_count)
        for moving_average in self.recv_bytes.values():
            moving_average.add_value(current_time, metric.recv_bytes)
        for moving_average in self.recv_num_msgs.values():
            moving_average.add_value(current_time, metric.recv_count)

    def log_averages(self, key: str):
        logger.info(f"Port: {key}")
        for interval, moving_average in self.send_bytes.items():
            moving_average.log_averages(interval, MetricType.THROUGHPUT, "Send")
        for interval, moving_average in self.send_num_msgs.items():
            moving_average.log_averages(interval, MetricType.MESSAGES, "Send")
        for interval, moving_average in self.recv_bytes.items():
            moving_average.log_averages(interval, MetricType.THROUGHPUT, "Recv")
        for interval, moving_average in self.recv_num_msgs.items():
            moving_average.log_averages(interval, MetricType.MESSAGES, "Recv")


async def metrics_watch(
    js: JetStreamContext, intervals: list[int], update_interval: int
):
    moving_averages: dict[str, PortMovingAverages] = {}
    bucket = await get_metrics_bucket(js)
    while True:
        keys = await get_keys(bucket)
        if not keys:
            await asyncio.sleep(update_interval)
            continue
        operator_keys = [key for key in keys if "." not in key]
        port_keys = [key for key in keys if "." in key]

        operator_futs = [get_val(bucket, key, OperatorMetrics) for key in operator_keys]
        port_futs = [get_val(bucket, key, PortMetrics) for key in port_keys]

        current_time = asyncio.get_event_loop().time()

        for fut in asyncio.as_completed(port_futs):
            metric = await fut
            if not metric:
                continue
            key = str(metric.id)

            if key not in moving_averages:
                moving_averages[key] = PortMovingAverages(intervals, update_interval)

            moving_averages[key].add_metrics(current_time, metric)
            moving_averages[key].log_averages(key)

        for fut in asyncio.as_completed(operator_futs):
            metric = await fut
            if not metric:
                logger.warning("Operator metric not found...")
                continue
            logger.info(f"Operator Key: {metric.id}")
            metric.timing.print_timing_info(logger)

        await asyncio.sleep(update_interval)


async def main():
    intervals = [2, 5, 30]  # List of intervals in seconds
    update_interval = 1  # Time difference between entries in seconds

    nc: NATSClient = await nats.connect(servers=[str(cfg.NATS_SERVER_URL)])
    js: JetStreamContext = nc.jetstream()

    logger.info("Metrics microservice is running...")

    await metrics_watch(js, intervals, update_interval)


if __name__ == "__main__":
    asyncio.run(main())
