import asyncio
import time
from uuid import UUID

import networkx
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg as NATSMsg
from nats.js import JetStreamContext
from nats.js.errors import NotFoundError
from networkx.readwrite.text import generate_network_text
from prometheus_client import start_http_server

from interactem.core.events.pipelines import PipelineRunVal
from interactem.core.logger import get_logger
from interactem.core.models.messages import (
    InputPortTrackingMetadata,
    MessageHeader,
    OperatorTrackingMetadata,
    OutputPortTrackingMetadata,
)
from interactem.core.models.operators import OperatorMetrics
from interactem.core.models.pipeline import PipelineJSON
from interactem.core.models.ports import PortMetrics
from interactem.core.nats import (
    consume_messages,
    create_or_update_stream,
    get_keys,
    get_metrics_bucket,
    get_pipelines_bucket,
    get_val,
    nc,
)
from interactem.core.nats.config import METRICS_STREAM_CONFIG
from interactem.core.nats.consumers import create_metrics_consumer
from interactem.core.pipeline import Pipeline
from interactem.metrics.prometheus_metrics import (
    CollectionDuration,
    EdgeConnection,
    ErrorType,
    OperatorProcessingTime,
    PipelineInfoData,
    PipelineStatus,
    ServiceStatus,
    record_collection_duration,
    record_collection_error,
    record_operator_processing_time,
    update_edge_connection,
    update_pipeline_info,
    update_pipeline_status,
    update_port_metrics,
    update_service_status,
)
from interactem.metrics.prometheus_metrics import PortMetrics as PrometheusPortMetrics

from .config import cfg

logger = get_logger()


async def metrics_watch(js: JetStreamContext, update_interval: int):
    metrics_bucket = await get_metrics_bucket(js)
    pipeline_bucket = await get_pipelines_bucket(js)

    while True:
        start_time = time.time()

        try:
            pipeline_keys = await get_keys(pipeline_bucket)
            if not pipeline_keys:
                record_collection_error(ErrorType(error_type="no_pipelines"))
                logger.info("No pipelines found...")
                await asyncio.sleep(update_interval)
                continue

            if len(pipeline_keys) > 1:
                record_collection_error(ErrorType(error_type="multiple_pipelines"))
                logger.error("More than one pipeline found...")
                await asyncio.sleep(update_interval)
                continue

            pipeline = await get_val(pipeline_bucket, pipeline_keys[0], PipelineRunVal)
            if not pipeline:
                record_collection_error(ErrorType(error_type="no_pipeline_data"))
                logger.info("No pipeline found...")
                await asyncio.sleep(update_interval)
                continue

            pipeline_data_with_id = {"id": pipeline.id, **pipeline.data}
            pipeline_data = PipelineJSON.model_validate(pipeline_data_with_id)

            pipeline_id = str(pipeline_data.id)
            pipeline_info_data = PipelineInfoData(info_data={
                'pipeline_id': pipeline_id,
                'operator_count': str(len(pipeline_data.operators)),
                'port_count': str(len(pipeline_data.ports)),
                'edge_count': str(len(pipeline_data.edges))
            })
            update_pipeline_info(pipeline_info_data)

            keys = await get_keys(metrics_bucket)
            if not keys:
                await asyncio.sleep(update_interval)
                continue

            operator_keys = [key for key in keys if "." not in key]
            port_keys = [key for key in keys if "." in key]

            operator_futs = [
                get_val(metrics_bucket, key, OperatorMetrics) for key in operator_keys
            ]
            port_metrics_map = {}
            port_futs = [get_val(metrics_bucket, key, PortMetrics) for key in port_keys]

            # Process port metrics - just send raw counters
            for fut in asyncio.as_completed(port_futs):
                metric = await fut
                if not metric:
                    continue
                key = str(metric.id)
                port_metrics_map[key] = metric

                operator_type = get_operator_type_for_port(metric.id, pipeline_data)

                # Send only raw metrics to Prometheus
                port_metrics_data = PrometheusPortMetrics(
                    port_id=key,
                    pipeline_id=pipeline_id,
                    operator_type=operator_type,
                    send_count=metric.send_count,
                    recv_count=metric.recv_count,
                    send_bytes=metric.send_bytes,
                    recv_bytes=metric.recv_bytes
                )
                update_port_metrics(port_metrics_data)

            for edge in pipeline_data.edges:
                input_metric = port_metrics_map.get(str(edge.input_id))
                output_metric = port_metrics_map.get(str(edge.output_id))
                if input_metric and output_metric:
                    # Just record that this edge exists
                    edge_connection = EdgeConnection(
                        input_port_id=str(edge.input_id),
                        output_port_id=str(edge.output_id),
                        pipeline_id=pipeline_id
                    )
                    update_edge_connection(edge_connection)

            pipeline_status_data = PipelineStatus(
                pipeline_id=pipeline_id,
                active_ports=len(port_metrics_map),
                active_operators=len(operator_keys)
            )
            update_pipeline_status(pipeline_status_data)

            # Process operator metrics
            for fut in asyncio.as_completed(operator_futs):
                metric = await fut
                if not metric:
                    logger.warning("Operator metric not found...")
                    continue

                if metric.timing and metric.timing.after_kernel and metric.timing.before_kernel:
                    processing_time = (metric.timing.after_kernel - metric.timing.before_kernel).microseconds
                    if processing_time > 0:
                        operator_type = get_operator_type_for_id(metric.id, pipeline_data)

                        processing_time_data = OperatorProcessingTime(
                            operator_id=str(metric.id),
                            pipeline_id=pipeline_id,
                            operator_type=operator_type,
                            processing_time_us=processing_time
                        )
                        record_operator_processing_time(processing_time_data)
                else:
                    logger.debug(f"Operator {metric.id} has incomplete timing data")

            collection_duration = time.time() - start_time
            duration_data = CollectionDuration(duration_seconds=collection_duration)
            record_collection_duration(duration_data)

            service_status_data = ServiceStatus(is_active=True)
            update_service_status(service_status_data)

            logger.debug(f"Metrics collection completed in {collection_duration:.3f}s")

        except Exception as e:
            logger.error(f"Error in metrics collection: {e}")
            record_collection_error(ErrorType(error_type="collection_exception"))
            update_service_status(ServiceStatus(is_active=False))

        await asyncio.sleep(update_interval)


def log_comparison(header: MessageHeader, pipeline: PipelineJSON):
    tracking = header.tracking
    if not tracking:
        logger.warning("No tracking information found...")
        return
    last_id = tracking[-1].id

    # Create a dictionary to map node IDs to their tracking metadata
    tracking_dict = {meta.id: meta for meta in tracking}

    try:
        pipeline_obj = Pipeline.from_pipeline(pipeline)
        # Check if last_id exists in the pipeline before creating subgraph
        if last_id not in pipeline_obj.nodes():
            logger.warning(f"Node {last_id} from tracking not found in pipeline graph. Available nodes: {list(pipeline_obj.nodes())}")
            return

        pipeline_obj = Pipeline.from_upstream_subgraph(pipeline_obj, last_id)
    except networkx.exception.NetworkXError as e:
        logger.error(f"NetworkX Error while creating pipeline subgraph: {e}")
        logger.error(f"last_id: {last_id}")
        logger.error(f"Available nodes in pipeline: {list(Pipeline.from_pipeline(pipeline).nodes()) if pipeline else 'No pipeline'}")
        return
    except Exception as e:
        logger.error(f"Unexpected error while creating pipeline subgraph: {e}")
        return

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
    pipeline = await get_val(pipeline_bucket, pipeline_keys[0], PipelineRunVal)
    if not pipeline:
        logger.info("No pipeline found...")
        return

    pipeline_data_with_id = {
        "id": pipeline.id,
        **pipeline.data
    }
    pipeline_data = PipelineJSON.model_validate(pipeline_data_with_id)

    data = MessageHeader.model_validate_json(msg.data.decode("utf-8"))
    try:
        log_comparison(data, pipeline_data)
    except networkx.exception.NetworkXError as e:
        logger.warning(f"Failed to log comparison... {str(e)}")


def get_operator_type_for_port(port_id: UUID, pipeline: PipelineJSON) -> str:
    for port in pipeline.ports:
        if port.id == port_id:
            for operator in pipeline.operators:
                if operator.id == port.operator_id:
                    return operator.image
    return "unknown"

def get_operator_type_for_id(operator_id: UUID, pipeline: PipelineJSON) -> str:
    for operator in pipeline.operators:
        if operator.id == operator_id:
            return operator.image
    return "unknown"


async def main():
    update_interval = 1  # Time between collections in seconds
    prometheus_port = cfg.METRICS_PORT

    nats_client: NATSClient = await nc(
        servers=[str(cfg.NATS_SERVER_URL)], name="metrics"
    )
    js: JetStreamContext = nats_client.jetstream()

    logger.info("Metrics microservice with Prometheus is starting...")

    start_http_server(prometheus_port)
    logger.info(f"Prometheus server started successfully on port {prometheus_port}")

    try:
        metrics_psub = await create_metrics_consumer(js)
    except NotFoundError:
        await create_or_update_stream(METRICS_STREAM_CONFIG, js)
        metrics_psub = await create_metrics_consumer(js)

    metrics_watch_task = asyncio.create_task(metrics_watch(js, update_interval))
    consume_messages_task = asyncio.create_task(
        consume_messages(metrics_psub, handler=handle_metrics, js=js)
    )

    await asyncio.gather(metrics_watch_task, consume_messages_task)


if __name__ == "__main__":
    asyncio.run(main())
