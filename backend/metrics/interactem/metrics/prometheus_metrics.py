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

class OperatorProcessingTime(BaseModel):
    operator_id: str
    pipeline_id: str
    operator_type: str
    processing_time_us: float = Field(ge=0, description="Processing time in microseconds")

class PipelineStatus(BaseModel):
    pipeline_id: str
    active_ports: int = Field(ge=0, description="Number of active ports")
    active_operators: int = Field(ge=0, description="Number of active operators")

class EdgeConnection(BaseModel):
    input_port_id: str
    output_port_id: str
    pipeline_id: str

class CollectionDuration(BaseModel):
    duration_seconds: float = Field(ge=0, description="Duration in seconds")

class ErrorType(BaseModel):
    error_type: str = Field(description="Type of error that occurred")

class PipelineInfoData(BaseModel):
    info_data: dict[str, str] = Field(description="Pipeline information key-value pairs")

class ServiceStatus(BaseModel):
    is_active: bool = Field(default=True, description="Whether service is active")

# Prometheus Metrics - Only raw counters and gauges
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

edge_active = Gauge(
    'interactem_edge_active',
    'Active edge connections (always 1 when edge exists)',
    ['input_port_id', 'output_port_id', 'pipeline_id']
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

def update_port_metrics(metrics: PortMetrics):
    labels = {
        'port_id': metrics.port_id,
        'pipeline_id': metrics.pipeline_id,
        'operator_type': metrics.operator_type
    }

    port_messages_sent_total.labels(**labels).set(metrics.send_count)
    port_messages_received_total.labels(**labels).set(metrics.recv_count)
    port_bytes_sent_total.labels(**labels).set(metrics.send_bytes)
    port_bytes_received_total.labels(**labels).set(metrics.recv_bytes)

def record_operator_processing_time(processing: OperatorProcessingTime):
    labels = {
        'operator_id': processing.operator_id,
        'pipeline_id': processing.pipeline_id,
        'operator_type': processing.operator_type
    }

    operator_processing_time_latest.labels(**labels).set(processing.processing_time_us)
    operator_processing_time_histogram.labels(**labels).observe(processing.processing_time_us)

def update_edge_connection(edge: EdgeConnection):
    edge_active.labels(
        input_port_id=edge.input_port_id,
        output_port_id=edge.output_port_id,
        pipeline_id=edge.pipeline_id
    ).set(1)

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
