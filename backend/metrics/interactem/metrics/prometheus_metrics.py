
from prometheus_client import Counter, Gauge, Histogram, Info
from pydantic import BaseModel, Field

from interactem.core.logger import get_logger

logger = get_logger()

class PortMetrics(BaseModel):
    port_id: str
    pipeline_id: str
    operator_type: str
    send_count: int = Field(ge=0, description="Total messages sent")
    recv_count: int = Field(ge=0, description="Total messages received")
    send_bytes: int = Field(ge=0, description="Total bytes sent")
    recv_bytes: int = Field(ge=0, description="Total bytes received")


class PortRates(BaseModel):
    port_id: str
    pipeline_id: str
    operator_type: str
    interval: str
    send_throughput: float = Field(ge=0, description="Send throughput in Mbps")
    recv_throughput: float = Field(ge=0, description="Receive throughput in Mbps")
    send_msg_rate: float = Field(ge=0, description="Send message rate per second")
    recv_msg_rate: float = Field(ge=0, description="Receive message rate per second")


class EdgeMetrics(BaseModel):
    input_port_id: str
    output_port_id: str
    pipeline_id: str
    message_diff: int = Field(description="Message difference between input and output")
    byte_diff: int = Field(description="Byte difference between input and output")
    throughput_diff: float = Field(description="Throughput difference in Mbps")


class OperatorProcessingTime(BaseModel):
    operator_id: str
    pipeline_id: str
    operator_type: str
    processing_time_us: float = Field(ge=0, description="Processing time in microseconds")


class PipelineStatus(BaseModel):
    pipeline_id: str
    active_ports: int = Field(ge=0, description="Number of active ports")
    active_operators: int = Field(ge=0, description="Number of active operators")


class CollectionDuration(BaseModel):
    duration_seconds: float = Field(ge=0, description="Duration in seconds")


class ErrorType(BaseModel):
    error_type: str = Field(description="Type of error that occurred")


class PipelineInfoData(BaseModel):
    info_data: dict[str, str] = Field(description="Pipeline information key-value pairs")


class ServiceStatus(BaseModel):
    is_active: bool = Field(default=True, description="Whether service is active")


# Prometheus Metrics
port_messages_sent_total = Gauge(
    'interactem_port_messages_sent_total',
    'Total messages sent through port',
    ['port_id', 'pipeline_id', 'operator_type']
)

port_messages_received_total = Gauge(
    'interactem_port_messages_received_total',
    'Total messages received through port',
    ['port_id', 'pipeline_id', 'operator_type']
)

port_bytes_sent_total = Gauge(
    'interactem_port_bytes_sent_total',
    'Total bytes sent through port',
    ['port_id', 'pipeline_id', 'operator_type']
)

port_bytes_received_total = Gauge(
    'interactem_port_bytes_received_total',
    'Total bytes received through port',
    ['port_id', 'pipeline_id', 'operator_type']
)

port_throughput_send_mbps = Gauge(
    'interactem_port_throughput_send_mbps',
    'Current send throughput in Mbps',
    ['port_id', 'pipeline_id', 'operator_type', 'interval']
)

port_throughput_recv_mbps = Gauge(
    'interactem_port_throughput_recv_mbps',
    'Current receive throughput in Mbps',
    ['port_id', 'pipeline_id', 'operator_type', 'interval']
)

port_message_rate_send = Gauge(
    'interactem_port_message_rate_send',
    'Current send message rate per second',
    ['port_id', 'pipeline_id', 'operator_type', 'interval']
)

port_message_rate_recv = Gauge(
    'interactem_port_message_rate_recv',
    'Current receive message rate per second',
    ['port_id', 'pipeline_id', 'operator_type', 'interval']
)

edge_message_diff = Gauge(
    'interactem_edge_message_diff',
    'Message difference between input and output ports',
    ['input_port_id', 'output_port_id', 'pipeline_id']
)

edge_byte_diff = Gauge(
    'interactem_edge_byte_diff',
    'Byte difference between input and output ports',
    ['input_port_id', 'output_port_id', 'pipeline_id']
)

edge_throughput_diff = Gauge(
    'interactem_edge_throughput_diff_mbps',
    'Throughput difference between input and output ports',
    ['input_port_id', 'output_port_id', 'pipeline_id']
)

operator_processing_time_histogram = Histogram(
    'interactem_operator_processing_time_histogram_microseconds',
    'Operator processing time histogram in microseconds',
    ['operator_id', 'pipeline_id', 'operator_type'],
    buckets=[1, 10, 100, 1000, 10000, 100000, 1000000, float('inf')]
)

operator_processing_time_latest = Gauge(
    'interactem_operator_processing_time_latest_microseconds',
    'Latest operator processing time in microseconds',
    ['operator_id', 'pipeline_id', 'operator_type']
)


pipeline_active_ports = Gauge(
    'interactem_pipeline_active_ports',
    'Number of active ports in pipeline',
    ['pipeline_id']
)

pipeline_active_operators = Gauge(
    'interactem_pipeline_active_operators',
    'Number of active operators in pipeline',
    ['pipeline_id']
)

service_status = Gauge(
    'interactem_service_status',
    'Service status (1=active, 0=inactive)',
    ['service']
)

metrics_collection_duration_seconds = Histogram(
    'interactem_metrics_collection_duration_seconds',
    'Time spent collecting metrics per cycle',
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, float('inf')]
)

metrics_collection_errors_total = Counter(
    'interactem_metrics_collection_errors_total',
    'Total number of metric collection errors',
    ['error_type']
)

pipeline_info = Info(
    'interactem_pipeline_info',
    'Information about the current pipeline'
)

# Initialize service as active
service_status.labels(service='metrics').set(1)

def update_metrics_batch(labels: dict, metric_value_pairs: list[tuple]):
    """Update multiple metrics with the same labels"""
    for metric, value in metric_value_pairs:
        metric.labels(**labels).set(value)

def update_port_metrics(metrics: PortMetrics):
    labels = {
        'port_id': metrics.port_id,
        'pipeline_id': metrics.pipeline_id,
        'operator_type': metrics.operator_type
    }

    metric_updates = [
        (port_messages_sent_total, metrics.send_count),
        (port_messages_received_total, metrics.recv_count),
        (port_bytes_sent_total, metrics.send_bytes),
        (port_bytes_received_total, metrics.recv_bytes)
    ]

    update_metrics_batch(labels, metric_updates)

def update_port_rates(rates: PortRates):
    labels = {
        'port_id': rates.port_id,
        'pipeline_id': rates.pipeline_id,
        'operator_type': rates.operator_type,
        'interval': rates.interval
    }

    metric_updates = [
        (port_throughput_send_mbps, rates.send_throughput),
        (port_throughput_recv_mbps, rates.recv_throughput),
        (port_message_rate_send, rates.send_msg_rate),
        (port_message_rate_recv, rates.recv_msg_rate)
    ]

    update_metrics_batch(labels, metric_updates)

def update_edge_metrics(edge: EdgeMetrics):
    labels = {
        'input_port_id': edge.input_port_id,
        'output_port_id': edge.output_port_id,
        'pipeline_id': edge.pipeline_id
    }

    metric_updates = [
        (edge_message_diff, edge.message_diff),
        (edge_byte_diff, edge.byte_diff),
        (edge_throughput_diff, edge.throughput_diff)
    ]

    update_metrics_batch(labels, metric_updates)


def record_operator_processing_time(processing: OperatorProcessingTime):
    operator_processing_time_latest.labels(
        operator_id=processing.operator_id,
        pipeline_id=processing.pipeline_id,
        operator_type=processing.operator_type
    ).set(processing.processing_time_us)

    operator_processing_time_histogram.labels(
        operator_id=processing.operator_id,
        pipeline_id=processing.pipeline_id,
        operator_type=processing.operator_type
    ).observe(processing.processing_time_us)


def update_pipeline_status(status: PipelineStatus):
    pipeline_active_ports.labels(pipeline_id=status.pipeline_id).set(status.active_ports)
    pipeline_active_operators.labels(pipeline_id=status.pipeline_id).set(status.active_operators)


def record_collection_duration(duration: CollectionDuration):
    metrics_collection_duration_seconds.observe(duration.duration_seconds)


def record_collection_error(error: ErrorType):
    service_status.labels(service='metrics').set(0)
    if error.error_type in ["no_pipelines", "no_pipeline_data"]:
        return
    metrics_collection_errors_total.labels(error_type=error.error_type).inc()


def update_pipeline_info(pipeline_data: PipelineInfoData):
    pipeline_info.info(pipeline_data.info_data)


def update_service_status(status: ServiceStatus):
    service_status.labels(service='metrics').set(1 if status.is_active else 0)
