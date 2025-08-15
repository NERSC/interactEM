from prometheus_client import Counter, Gauge, Histogram
from pydantic import BaseModel, Field

from interactem.core.logger import get_logger
from interactem.core.models.metrics import OperatorMetrics, PortMetrics

logger = get_logger()

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

runtime_port_messages_sent_total = Gauge(
    'interactem_runtime_port_messages_sent_total',
    'Total messages sent on a single runtime port instance',
    ['runtime_port_id','port_id','pipeline_id','operator_type']
)
runtime_port_messages_received_total = Gauge(
    'interactem_runtime_port_messages_received_total',
    'Total messages received on a single runtime port instance',
    ['runtime_port_id','port_id','pipeline_id','operator_type']
)
runtime_port_bytes_sent_total = Gauge(
    'interactem_runtime_port_bytes_sent_total',
    'Total bytes sent on a single runtime port instance',
    ['runtime_port_id','port_id','pipeline_id','operator_type']
)
runtime_port_bytes_received_total = Gauge(
    'interactem_runtime_port_bytes_received_total',
    'Total bytes received on a single runtime port instance',
    ['runtime_port_id','port_id','pipeline_id','operator_type']
)

runtime_operator_processing_time_latest = Gauge(
    'interactem_runtime_operator_processing_time_latest_microseconds',
    'Latest operator processing time on a single runtime operator instance',
    ['runtime_operator_id','operator_id','pipeline_id','operator_type']
)
runtime_operator_processing_time_histogram = Histogram(
    'interactem_runtime_operator_processing_time_histogram_microseconds',
    'Operator processing time histogram per‐runtime instance',
    ['runtime_operator_id','operator_id','pipeline_id','operator_type'],
    buckets=[1,10,100,1000,10000,100000,1000000,float('inf')]
)

service_status.labels(service='metrics').set(1)

def update_runtime_port_metrics(port_metrics: PortMetrics, pipeline_id: str, operator_label: str):
    labels = {
        'runtime_port_id': str(port_metrics.id),
        'port_id': str(port_metrics.canonical_id),
        'pipeline_id': pipeline_id,
        'operator_type': operator_label
    }
    runtime_port_messages_sent_total.labels(**labels).set(port_metrics.send_count)
    runtime_port_messages_received_total.labels(**labels).set(port_metrics.recv_count)
    runtime_port_bytes_sent_total.labels(**labels).set(port_metrics.send_bytes)
    runtime_port_bytes_received_total.labels(**labels).set(port_metrics.recv_bytes)

def record_runtime_operator_processing_time(op_metrics : OperatorMetrics, pipeline_id: str, operator_label: str):
    labels = {
        'runtime_operator_id': op_metrics.id,
        'operator_id': op_metrics.canonical_id,
        'pipeline_id': pipeline_id,
        'operator_type': operator_label
    }
    processing_time_us = (op_metrics.timing.after_kernel - op_metrics.timing.before_kernel).microseconds
    if processing_time_us > 0:
        runtime_operator_processing_time_latest.labels(**labels).set(processing_time_us)
        runtime_operator_processing_time_histogram.labels(**labels).observe(processing_time_us)

def update_pipeline_status(status: PipelineStatus):
    pipeline_active_ports.labels(pipeline_id=status.pipeline_id).set(status.active_ports)
    pipeline_active_operators.labels(pipeline_id=status.pipeline_id).set(status.active_operators)

def record_collection_duration(duration: CollectionDuration):
    metrics_collection_duration_seconds.observe(duration.duration_seconds)

def record_collection_error(error: ErrorType):
    service_status.labels(service='metrics').set(0)
    # don’t increment for “no_pipelines” or “no_pipeline_data”, not counted as errors
    if error.error_type not in ('no_pipelines','no_pipeline_data'):
        metrics_collection_errors_total.labels(error_type=error.error_type).inc()

def update_service_status(status: ServiceStatus):
    service_status.labels(service='metrics').set(1 if status.is_active else 0)
