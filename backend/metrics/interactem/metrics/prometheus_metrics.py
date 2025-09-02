from enum import Enum
from uuid import UUID

from prometheus_client import Counter, Gauge, Histogram
from pydantic import BaseModel, Field

from interactem.core.logger import get_logger
from interactem.core.models.metrics import OperatorMetrics, PortMetrics

logger = get_logger()


class PortMetricLabelsSchema(BaseModel):
    runtime_port_id: UUID
    port_id: UUID
    pipeline_id: UUID
    operator_label: str


class OperatorMetricLabelsSchema(BaseModel):
    runtime_operator_id: UUID
    operator_id: UUID
    pipeline_id: UUID
    operator_label: str


class PipelineMetricLabelsSchema(BaseModel):
    pipeline_id: UUID


class ServiceMetricLabelsSchema(BaseModel):
    service: str = Field(default="metrics")


class ErrorMetricLabelsSchema(BaseModel):
    error_type: str


class PipelineActivity(BaseModel):
    pipeline_id: UUID
    active_ports: int = Field(ge=0, description="Number of active ports")
    active_operators: int = Field(ge=0, description="Number of active operators")


class ErrorTypeEnum(str, Enum):
    NO_PIPELINES = "no_pipelines"
    MULTIPLE_PIPELINES = "multiple_pipelines"
    NO_PIPELINE_DATA = "no_pipeline_data"
    COLLECTION_EXCEPTION = "collection_exception"


class ErrorType(BaseModel):
    error_type: ErrorTypeEnum = Field(description="Type of error that occurred")


class ServiceStatus(BaseModel):
    is_active: bool = Field(default=True, description="Whether any pipeline is active")


# Metric definitions using class attributes
pipeline_active_ports = Gauge(
    "interactem_pipeline_active_ports",
    "Number of active ports in pipeline",
    [*PipelineMetricLabelsSchema.model_fields],
)

pipeline_active_operators = Gauge(
    "interactem_pipeline_active_operators",
    "Number of active operators in pipeline",
    [*PipelineMetricLabelsSchema.model_fields],
)

service_status = Gauge(
    "interactem_service_status",
    "Service status (1=active, 0=inactive)",
    [*ServiceMetricLabelsSchema.model_fields],
)

metrics_collection_duration_seconds = Histogram(
    "interactem_metrics_collection_duration_seconds",
    "Time spent collecting metrics per cycle",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, float("inf")],
)

metrics_collection_errors_total = Counter(
    "interactem_metrics_collection_errors_total",
    "Total number of metric collection errors",
    [*ErrorMetricLabelsSchema.model_fields],
)

runtime_port_messages_sent_total = Gauge(
    "interactem_runtime_port_messages_sent_total",
    "Total messages sent on a single runtime port instance",
    [*PortMetricLabelsSchema.model_fields],
)

runtime_port_messages_received_total = Gauge(
    "interactem_runtime_port_messages_received_total",
    "Total messages received on a single runtime port instance",
    [*PortMetricLabelsSchema.model_fields],
)

runtime_port_bytes_sent_total = Gauge(
    "interactem_runtime_port_bytes_sent_total",
    "Total bytes sent on a single runtime port instance",
    [*PortMetricLabelsSchema.model_fields],
)

runtime_port_bytes_received_total = Gauge(
    "interactem_runtime_port_bytes_received_total",
    "Total bytes received on a single runtime port instance",
    [*PortMetricLabelsSchema.model_fields],
)

runtime_operator_processing_time_latest = Gauge(
    "interactem_runtime_operator_processing_time_latest_microseconds",
    "Latest operator processing time on a single runtime operator instance",
    [*OperatorMetricLabelsSchema.model_fields],
)

runtime_operator_processing_time_histogram = Histogram(
    "interactem_runtime_operator_processing_time_histogram_microseconds",
    "Operator processing time histogram per‐runtime instance",
    [*OperatorMetricLabelsSchema.model_fields],
    buckets=[1, 10, 100, 1000, 10000, 100000, 1000000, float("inf")],
)

# Initialize service status
_initial_service_labels = ServiceMetricLabelsSchema()
service_status.labels(**_initial_service_labels.model_dump()).set(1)


def update_runtime_port_metrics(
    port_metrics: PortMetrics, pipeline_id: UUID, operator_label: str
):
    labels = PortMetricLabelsSchema(
        runtime_port_id=port_metrics.id,
        port_id=port_metrics.canonical_id,
        pipeline_id=pipeline_id,
        operator_label=operator_label,
    )
    labels_dict = labels.model_dump()

    runtime_port_messages_sent_total.labels(**labels_dict).set(port_metrics.send_count)
    runtime_port_messages_received_total.labels(**labels_dict).set(
        port_metrics.recv_count
    )
    runtime_port_bytes_sent_total.labels(**labels_dict).set(port_metrics.send_bytes)
    runtime_port_bytes_received_total.labels(**labels_dict).set(port_metrics.recv_bytes)


def record_runtime_operator_processing_time(
    op_metrics: OperatorMetrics, pipeline_id: UUID, operator_label: str
):
    labels = OperatorMetricLabelsSchema(
        runtime_operator_id=op_metrics.id,
        operator_id=op_metrics.canonical_id,
        pipeline_id=pipeline_id,
        operator_label=operator_label,
    )
    labels_dict = labels.model_dump()

    processing_time_us = (
        op_metrics.timing.after_kernel - op_metrics.timing.before_kernel
    ).microseconds
    if processing_time_us > 0:
        runtime_operator_processing_time_latest.labels(**labels_dict).set(
            processing_time_us
        )
        runtime_operator_processing_time_histogram.labels(**labels_dict).observe(
            processing_time_us
        )


def update_pipeline_state(state: PipelineActivity):
    labels = PipelineMetricLabelsSchema(pipeline_id=state.pipeline_id)
    labels_dict = labels.model_dump()

    pipeline_active_ports.labels(**labels_dict).set(state.active_ports)
    pipeline_active_operators.labels(**labels_dict).set(state.active_operators)


def record_collection_duration(duration_seconds: float):
    metrics_collection_duration_seconds.observe(duration_seconds)


def record_collection_error(error: ErrorType):
    service_labels = ServiceMetricLabelsSchema()
    service_status.labels(**service_labels.model_dump()).set(0)

    # Don't increment for "no_pipelines" or "no_pipeline_data", not counted as errors
    if error.error_type not in (
        ErrorTypeEnum.NO_PIPELINES,
        ErrorTypeEnum.NO_PIPELINE_DATA,
    ):
        error_labels = ErrorMetricLabelsSchema(error_type=error.error_type.value)
        metrics_collection_errors_total.labels(**error_labels.model_dump()).inc()


def update_service_status(status: ServiceStatus):
    service_labels = ServiceMetricLabelsSchema()
    service_status.labels(**service_labels.model_dump()).set(
        1 if status.is_active else 0
    )
