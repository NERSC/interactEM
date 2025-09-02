import asyncio
import time
from uuid import UUID

import networkx
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg as NATSMsg
from nats.js import JetStreamContext
from networkx.readwrite.text import generate_network_text
from prometheus_client import start_http_server

from interactem.core.constants import (
    PIPELINES,
)
from interactem.core.logger import get_logger
from interactem.core.models.kvs import PipelineRunVal
from interactem.core.models.messages import (
    InputPortTrackingMetadata,
    MessageHeader,
    OperatorTrackingMetadata,
    OutputPortTrackingMetadata,
)
from interactem.core.models.metrics import OperatorMetrics, PortMetrics
from interactem.core.models.runtime import RuntimePipeline
from interactem.core.nats import (
    consume_messages,
    get_keys,
    get_metrics_bucket,
    get_status_bucket,
    get_val,
    nc,
)
from interactem.core.nats.consumers import create_metrics_consumer
from interactem.core.pipeline import Pipeline
from interactem.metrics.prometheus_metrics import (
    ErrorType,
    ErrorTypeEnum,
    PipelineActivity,
    ServiceStatus,
    record_collection_duration,
    record_collection_error,
    record_runtime_operator_processing_time,
    update_pipeline_state,
    update_runtime_port_metrics,
    update_service_status,
)

from .config import cfg

logger = get_logger()


async def metrics_watch(js: JetStreamContext, update_interval: int):
    metrics_bucket = await get_metrics_bucket(js)
    pipeline_bucket = await get_status_bucket(js)

    while True:
        start_time = time.time()

        try:
            pipeline_keys = await get_keys(pipeline_bucket, filters=[f"{PIPELINES}"])
            if not pipeline_keys:
                record_collection_error(
                    ErrorType(error_type=ErrorTypeEnum.NO_PIPELINES)
                )
                logger.info("No pipelines found...")
                await asyncio.sleep(update_interval)
                continue

            if len(pipeline_keys) > 1:
                record_collection_error(
                    ErrorType(error_type=ErrorTypeEnum.MULTIPLE_PIPELINES)
                )
                logger.error("More than one pipeline found...")
                await asyncio.sleep(update_interval)
                continue

            pipeline = await get_val(pipeline_bucket, pipeline_keys[0], PipelineRunVal)
            if not pipeline:
                record_collection_error(
                    ErrorType(error_type=ErrorTypeEnum.NO_PIPELINE_DATA)
                )
                logger.info("No pipeline found...")
                await asyncio.sleep(update_interval)
                continue

            valid_pipeline = pipeline.pipeline
            pipeline_canonical_id = valid_pipeline.canonical_id

            keys = await get_keys(metrics_bucket)
            if not keys:
                await asyncio.sleep(update_interval)
                continue

            operator_keys = [key for key in keys if key.startswith("op.")]
            port_keys = [key for key in keys if key.startswith("port.")]

            operator_futs = [
                get_val(metrics_bucket, key, OperatorMetrics) for key in operator_keys
            ]
            port_futs = [get_val(metrics_bucket, key, PortMetrics) for key in port_keys]

            # Process port metrics - just send raw counters with pipeline and operator context
            for fut in asyncio.as_completed(port_futs):
                metric = await fut
                if not metric:
                    continue
                operator_label = valid_pipeline.get_operator_label_by_port_id(metric.id)
                update_runtime_port_metrics(
                    metric, pipeline_canonical_id, operator_label
                )

            # Process operator metrics - send timing with pipeline and operator context
            for of in asyncio.as_completed(operator_futs):
                metric = await of
                if not metric:
                    logger.info("Operator metric not found...")
                    continue
                if metric.timing.after_kernel and metric.timing.before_kernel:
                    operator_label = valid_pipeline.get_operator_label_by_id(metric.id)
                    record_runtime_operator_processing_time(
                        metric, pipeline_canonical_id, operator_label
                    )
                else:
                    logger.info(
                        f"Operator {metric.canonical_id} has incomplete timing data"
                    )

            pipeline_status_data = PipelineActivity(
                pipeline_id=pipeline_canonical_id,
                active_ports=len(port_keys),
                active_operators=len(operator_keys),
            )
            update_pipeline_state(pipeline_status_data)

            collection_duration = time.time() - start_time
            record_collection_duration(collection_duration)

            service_status_data = ServiceStatus(is_active=True)
            update_service_status(service_status_data)

            logger.debug(f"Metrics collection completed in {collection_duration:.3f}s")

        except Exception as e:
            logger.error(f"Error in metrics collection: {e}")
            record_collection_error(
                ErrorType(error_type=ErrorTypeEnum.COLLECTION_EXCEPTION)
            )
            update_service_status(ServiceStatus(is_active=False))

        await asyncio.sleep(update_interval)


def log_comparison(header: MessageHeader, pipeline: RuntimePipeline):
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

    for node in pipeline_obj.nodes():
        pipeline_obj.nodes[node]["label"] = str(node)

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
    pipeline_bucket = await get_status_bucket(js)
    pipeline_keys = await get_keys(pipeline_bucket, filters=[f"{PIPELINES}"])
    if not pipeline_keys:
        logger.debug("No pipelines found...")
        return
    if len(pipeline_keys) > 1:
        logger.error("More than one pipeline found...")
        return
    pipeline = await get_val(pipeline_bucket, pipeline_keys[0], PipelineRunVal)
    if not pipeline:
        logger.debug("No pipeline found...")
        return

    valid_pipeline = pipeline.pipeline

    data = MessageHeader.model_validate_json(msg.data.decode("utf-8"))
    try:
        log_comparison(data, valid_pipeline)
    except networkx.exception.NetworkXError as e:
        logger.warning(f"Failed to log comparison... {str(e)}")


async def main():
    update_interval = 1  # Time between collections in seconds
    prometheus_port = cfg.PROMETHEUS_PORT

    nats_client: NATSClient = await nc(
        servers=[str(cfg.NATS_SERVER_URL)], name="metrics"
    )
    js: JetStreamContext = nats_client.jetstream()

    logger.info("Metrics microservice with Prometheus is starting...")

    start_http_server(prometheus_port)
    logger.info(f"Prometheus server started successfully on port {prometheus_port}")

    metrics_psub = await create_metrics_consumer(js)

    metrics_watch_task = asyncio.create_task(metrics_watch(js, update_interval))
    consume_messages_task = asyncio.create_task(
        consume_messages(metrics_psub, handler=handle_metrics, js=js)
    )

    await asyncio.gather(metrics_watch_task, consume_messages_task)


if __name__ == "__main__":
    asyncio.run(main())
