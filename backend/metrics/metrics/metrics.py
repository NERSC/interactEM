import asyncio
from collections import deque
from enum import Enum
from uuid import UUID

import nats
import networkx
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg as NATSMsg
from nats.js import JetStreamContext
from nats.js.api import ConsumerConfig, DeliverPolicy
from networkx.readwrite.text import generate_network_text
from pydantic import BaseModel

from core.constants import STREAM_METRICS
from core.logger import get_logger
from core.models.base import IdType
from core.models.messages import (
    InputPortTrackingMetadata,
    MessageHeader,
    OperatorTrackingMetadata,
    OutputPortTrackingMetadata,
)
from core.models.operators import OperatorMetrics  # Import the OperatorMetrics model
from core.models.pipeline import PipelineJSON
from core.models.ports import PortMetrics
from core.nats import (
    consume_messages,
    get_keys,
    get_metrics_bucket,
    get_pipelines_bucket,
    get_val,
)
from core.pipeline import Pipeline

from .config import cfg

logger = get_logger("metrics", "DEBUG")

class MetricType(str, Enum):
    THROUGHPUT = "throughput (Mbps)"
    MESSAGES = "msgs (msgs/s)"

class EdgeMetric(BaseModel):
    input_id: IdType
    input_num_msgs: int = 0
    input_num_bytes: int = 0
    input_throughput: float = 0.0
    input_avg_msgs: float = 0.0
    output_id: IdType
    output_num_msgs: int = 0
    output_num_bytes: int = 0
    output_throughput: float = 0.0
    output_avg_msgs: float = 0.0

    def calculate_differences(self):
        message_diff = self.input_num_msgs - self.output_num_msgs
        byte_diff = self.input_num_bytes - self.output_num_bytes
        throughput_diff = self.input_throughput - self.output_throughput
        avg_msgs_diff = self.input_avg_msgs - self.output_avg_msgs
        return {
            "message_diff": message_diff,
            "byte_diff": byte_diff,
            "throughput_diff": throughput_diff,
            "avg_msgs_diff": avg_msgs_diff,
        }

    def log_metrics(self):
        logger.info(f"Edge from {self.input_id} to {self.output_id}:")
        logger.info(f"  Sent {self.input_num_msgs} msgs, {self.input_num_bytes} bytes")
        logger.info(
            f"  Received {self.output_num_msgs} msgs, {self.output_num_bytes} bytes"
        )

        differences = self.calculate_differences()
        logger.info(f"  Message diff: {differences['message_diff']}")
        logger.info(f"  Byte diff: {differences['byte_diff']}")
        logger.info(f"  Throughput diff: {differences['throughput_diff']:.2f} Mbps")
        logger.info(f"  Avg msgs diff: {differences['avg_msgs_diff']:.2f}")
        logger.info(f"  Input throughput: {self.input_throughput:.2f} Mbps")
        logger.info(f"  Input average msgs: {self.input_avg_msgs:.2f}")
        logger.info(f"  Output throughput: {self.output_throughput:.2f} Mbps")
        logger.info(f"  Output average msgs: {self.output_avg_msgs:.2f}")

    @classmethod
    def from_io_and_moving_average(
        cls,
        input_metric: PortMetrics,
        output_metric: PortMetrics,
        input_moving_avg: "PortMovingAverages",
        output_moving_avg: "PortMovingAverages",
    ):
        return cls(
            input_id=input_metric.id,
            input_num_msgs=input_metric.send_count,
            input_num_bytes=input_metric.send_bytes,
            input_throughput=input_moving_avg.send_bytes["2s"].average_throughput(),
            input_avg_msgs=input_moving_avg.send_num_msgs["2s"].average_msgs(),
            output_id=output_metric.id,
            output_num_msgs=output_metric.recv_count,
            output_num_bytes=output_metric.recv_bytes,
            output_throughput=output_moving_avg.recv_bytes["2s"].average_throughput(),
            output_avg_msgs=output_moving_avg.recv_num_msgs["2s"].average_msgs(),
        )


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

    def average_msgs(self) -> float:
        if not self.values:
            return 0.0
        total_msgs = self.values[-1][1] - self.values[0][1]
        total_time = self.values[-1][0] - self.values[0][0]
        return total_msgs / total_time if total_time > 0 else 0.0

    def log_averages(self, interval: str, metric_type: MetricType, direction: str):
        metric_types = {
            MetricType.THROUGHPUT: self.average_throughput,
            MetricType.MESSAGES: self.average_msgs,
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
    metrics_bucket = await get_metrics_bucket(js)
    pipeline_bucket = await get_pipelines_bucket(js)

    while True:
        pipeline_keys = await get_keys(pipeline_bucket)
        if not pipeline_keys:
            logger.info("No pipelines found...")
            await asyncio.sleep(update_interval)
            continue

        if len(pipeline_keys) > 1:
            logger.error("More than one pipeline found...")
            await asyncio.sleep(update_interval)
            continue

        pipeline = await get_val(pipeline_bucket, pipeline_keys[0], PipelineJSON)
        if not pipeline:
            logger.info("No pipeline found...")
            await asyncio.sleep(update_interval)
            continue

        keys = await get_keys(metrics_bucket)
        if not keys:
            await asyncio.sleep(update_interval)
            continue

        operator_keys = [key for key in keys if "." not in key]
        port_keys = [key for key in keys if "." in key]
        edge_metrics: list[EdgeMetric] = []

        operator_futs = [
            get_val(metrics_bucket, key, OperatorMetrics) for key in operator_keys
        ]
        port_metrics_map = {}
        port_futs = [get_val(metrics_bucket, key, PortMetrics) for key in port_keys]

        current_time = asyncio.get_event_loop().time()

        for fut in asyncio.as_completed(port_futs):
            metric = await fut
            if not metric:
                continue
            key = str(metric.id)
            port_metrics_map[key] = metric

            if key not in moving_averages:
                moving_averages[key] = PortMovingAverages(intervals, update_interval)

            moving_averages[key].add_metrics(current_time, metric)
            # moving_averages[key].log_averages(key)

        # Match edges to port metrics
        for edge in pipeline.edges:
            input_metric = port_metrics_map.get(str(edge.input_id))
            output_metric = port_metrics_map.get(str(edge.output_id))
            if input_metric and output_metric:
                input_moving_avg = moving_averages.get(str(edge.input_id))
                output_moving_avg = moving_averages.get(str(edge.output_id))

                if input_moving_avg and output_moving_avg:
                    edge_metric = EdgeMetric.from_io_and_moving_average(
                        input_metric, output_metric, input_moving_avg, output_moving_avg
                    )
                    edge_metrics.append(edge_metric)

        # for edge_metric in edge_metrics:
        #     # edge_metric.log_metrics()
        #     pass

        for fut in asyncio.as_completed(operator_futs):
            metric = await fut
            if not metric:
                logger.warning("Operator metric not found...")
                continue
            # logger.info(f"Operator Key: {metric.id}")
            # metric.timing.print_timing_info(logger)

        await asyncio.sleep(update_interval)

def log_comparison(header: MessageHeader, pipeline: PipelineJSON):
    tracking = header.tracking
    if not tracking:
        logger.warning("No tracking information found...")
        return
    last_id = tracking[-1].id

    # Create a dictionary to map node IDs to their tracking metadata
    tracking_dict = {meta.id: meta for meta in tracking}

    pipeline_obj = Pipeline.from_pipeline(pipeline)
    pipeline_obj = Pipeline.from_upstream_subgraph(pipeline_obj, last_id)

    previous_node_id = None
    previous_metadata = None
    first_line = True
    # TODO: do better
    for line in generate_network_text(pipeline_obj):
        node_id = UUID(line.split()[-1])
        image = None
        for idx, id in enumerate([op.id for op in pipeline.operators]):
            if id == node_id:
                image = pipeline.operators[idx].image
                break
        for idx, id in enumerate([op.id for op in pipeline.ports]):
            if id == node_id:
                op_id = pipeline.ports[idx].operator_id
                for idx_op, id_op in enumerate([op.id for op in pipeline.operators]):
                    if id_op == op_id:
                        image = pipeline.operators[idx_op].image
                        break
        logger.info([line, image])

        # Print the tracking information for the node
        if node_id in tracking_dict:
            metadata = tracking_dict[node_id]
            if not first_line:
                previous_metadata = tracking_dict.get(previous_node_id, None)  # type: ignore
            if isinstance(metadata, OperatorTrackingMetadata):
                if metadata.time_after_operate and metadata.time_before_operate:
                    logger.info(
                        f"  Operate time (per frame): {(metadata.time_after_operate - metadata.time_before_operate).microseconds}"
                    )
            elif isinstance(metadata, InputPortTrackingMetadata):
                if metadata.time_after_header_validate:
                    logger.info(
                        f"  Time After Header Validate: {metadata.time_after_header_validate}"
                    )
                if isinstance(previous_metadata, OutputPortTrackingMetadata):
                    if previous_metadata and previous_metadata.time_before_send:
                        time_diff = (
                            metadata.time_after_header_validate
                            - previous_metadata.time_before_send
                        ).microseconds
                        logger.info(f"  Time between ports: {time_diff}")

            elif isinstance(metadata, OutputPortTrackingMetadata):
                if metadata.time_before_send:
                    logger.info(f"  Time Before Send: {metadata.time_before_send}")

        if first_line:
            first_line = False
        previous_node_id = node_id


async def handle_metrics(msg: NATSMsg, js: JetStreamContext):
    await msg.ack()
    pipeline_bucket = await get_pipelines_bucket(js)
    pipeline_keys = await get_keys(pipeline_bucket)
    if not pipeline_keys:
        logger.info("No pipelines found...")
        return
    if len(pipeline_keys) > 1:
        logger.error("More than one pipeline found...")
        return
    pipeline = await get_val(pipeline_bucket, pipeline_keys[0], PipelineJSON)
    if not pipeline:
        logger.info("No pipeline found...")
        return

    data = MessageHeader.model_validate_json(msg.data.decode("utf-8"))
    try:
        log_comparison(data, pipeline)
    except networkx.exception.NetworkXError:
        logger.warning("Failed to log comparison...")
    # for port_id, metrics in data.items():
    #     port_metrics = PortMetrics.model_validate_json(metrics)
    #     logger.info(f"Received metrics for port {port_id}: {port_metrics}")

async def main():
    intervals = [2, 5, 30]  # List of intervals in seconds
    update_interval = 1  # Time difference between entries in seconds

    nc: NATSClient = await nats.connect(servers=[str(cfg.NATS_SERVER_URL)])
    js: JetStreamContext = nc.jetstream()

    logger.info("Metrics microservice is running...")

    consumer_cfg = ConsumerConfig(
        description=f"orchestrator-{id}", deliver_policy=DeliverPolicy.LAST_PER_SUBJECT
    )
    metrics_psub = await js.pull_subscribe(
        subject=f"{STREAM_METRICS}.>", config=consumer_cfg
    )

    metrics_watch_task = asyncio.create_task(
        metrics_watch(js, intervals, update_interval)
    )
    consume_messages_task = asyncio.create_task(
        consume_messages(metrics_psub, handler=handle_metrics, js=js)
    )

    await asyncio.gather(metrics_watch_task, consume_messages_task)


if __name__ == "__main__":
    asyncio.run(main())
