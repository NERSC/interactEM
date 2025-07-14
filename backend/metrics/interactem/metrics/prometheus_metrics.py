import time

from prometheus_client import Counter, Gauge, Histogram, Info

from interactem.core.logger import get_logger

logger = get_logger()

class InteractemPrometheusMetrics:

    def __init__(self):
        # Port Metrics - Counters (cumulative)
        self.port_messages_sent_total = Counter(
            'interactem_port_messages_sent_total',
            'Total messages sent through port',
            ['port_id', 'pipeline_id', 'operator_type']
        )

        self.port_messages_received_total = Counter(
            'interactem_port_messages_received_total',
            'Total messages received through port',
            ['port_id', 'pipeline_id', 'operator_type']
        )

        self.port_bytes_sent_total = Counter(
            'interactem_port_bytes_sent_total',
            'Total bytes sent through port',
            ['port_id', 'pipeline_id', 'operator_type']
        )

        self.port_bytes_received_total = Counter(
            'interactem_port_bytes_received_total',
            'Total bytes received through port',
            ['port_id', 'pipeline_id', 'operator_type']
        )

        # Port Metrics - Gauges (current values)
        self.port_throughput_send_mbps = Gauge(
            'interactem_port_throughput_send_mbps',
            'Current send throughput in Mbps',
            ['port_id', 'pipeline_id', 'operator_type', 'interval']
        )

        self.port_throughput_recv_mbps = Gauge(
            'interactem_port_throughput_recv_mbps',
            'Current receive throughput in Mbps',
            ['port_id', 'pipeline_id', 'operator_type', 'interval']
        )

        self.port_message_rate_send = Gauge(
            'interactem_port_message_rate_send',
            'Current send message rate per second',
            ['port_id', 'pipeline_id', 'operator_type', 'interval']
        )

        self.port_message_rate_recv = Gauge(
            'interactem_port_message_rate_recv',
            'Current receive message rate per second',
            ['port_id', 'pipeline_id', 'operator_type', 'interval']
        )

        # Edge Metrics
        self.edge_message_diff = Gauge(
            'interactem_edge_message_diff',
            'Message difference between input and output ports',
            ['input_port_id', 'output_port_id', 'pipeline_id']
        )

        self.edge_byte_diff = Gauge(
            'interactem_edge_byte_diff',
            'Byte difference between input and output ports',
            ['input_port_id', 'output_port_id', 'pipeline_id']
        )

        self.edge_throughput_diff = Gauge(
            'interactem_edge_throughput_diff_mbps',
            'Throughput difference between input and output ports',
            ['input_port_id', 'output_port_id', 'pipeline_id']
        )

        # Operator Metrics
        self.operator_processing_time_histogram = Histogram(
            'interactem_operator_processing_time_histogram_microseconds',
            'Operator processing time histogram in microseconds',
            ['operator_id', 'pipeline_id', 'operator_type'],
            buckets=[1, 10, 100, 1000, 10000, 100000, 1000000, float('inf')]
        )

        self.operator_processing_time_latest = Gauge(
            'interactem_operator_processing_time_latest_microseconds',
            'Latest operator processing time in microseconds',
            ['operator_id', 'pipeline_id', 'operator_type']
        )


        # Pipeline Status
        self.pipeline_active_ports = Gauge(
            'interactem_pipeline_active_ports',
            'Number of active ports in pipeline',
            ['pipeline_id']
        )

        self.pipeline_active_operators = Gauge(
            'interactem_pipeline_active_operators',
            'Number of active operators in pipeline',
            ['pipeline_id']
        )

        # Service Status
        self.service_status = Gauge(
            'interactem_service_status',
            'Service status (1=active, 0=inactive)',
            ['service']
        )

        self.service_uptime_seconds = Gauge(
            'interactem_service_uptime_seconds',
            'Service uptime in seconds',
            ['service']
        )

        # System Metrics
        self.metrics_collection_duration_seconds = Histogram(
            'interactem_metrics_collection_duration_seconds',
            'Time spent collecting metrics per cycle',
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, float('inf')]
        )

        self.metrics_collection_errors_total = Counter(
            'interactem_metrics_collection_errors_total',
            'Total number of metric collection errors',
            ['error_type']
        )

        # Pipeline Info
        self.pipeline_info = Info(
            'interactem_pipeline_info',
            'Information about the current pipeline'
        )

        # Initialize service as active
        self.start_time = time.time()
        self.service_status.labels(service='metrics').set(1)

    def update_port_metrics(self, port_id: str, pipeline_id: str, operator_type: str,
                           send_count: int, recv_count: int, send_bytes: int, recv_bytes: int):
        """Update port counter metrics"""
        labels = {'port_id': port_id, 'pipeline_id': pipeline_id, 'operator_type': operator_type}

        # Set counters to current values (they track cumulative totals)
        self.port_messages_sent_total.labels(**labels)._value._value = send_count
        self.port_messages_received_total.labels(**labels)._value._value = recv_count
        self.port_bytes_sent_total.labels(**labels)._value._value = send_bytes
        self.port_bytes_received_total.labels(**labels)._value._value = recv_bytes

    def update_port_rates(self, port_id: str, pipeline_id: str, operator_type: str,
                         interval: str, send_throughput: float, recv_throughput: float,
                         send_msg_rate: float, recv_msg_rate: float):
        """Update port rate gauge metrics"""
        labels = {'port_id': port_id, 'pipeline_id': pipeline_id, 'operator_type': operator_type, 'interval': interval}

        self.port_throughput_send_mbps.labels(**labels).set(send_throughput)
        self.port_throughput_recv_mbps.labels(**labels).set(recv_throughput)
        self.port_message_rate_send.labels(**labels).set(send_msg_rate)
        self.port_message_rate_recv.labels(**labels).set(recv_msg_rate)

    def update_edge_metrics(self, input_port_id: str, output_port_id: str, pipeline_id: str,
                           message_diff: int, byte_diff: int, throughput_diff: float):
        """Update edge metrics"""
        labels = {'input_port_id': input_port_id, 'output_port_id': output_port_id, 'pipeline_id': pipeline_id}

        self.edge_message_diff.labels(**labels).set(message_diff)
        self.edge_byte_diff.labels(**labels).set(byte_diff)
        self.edge_throughput_diff.labels(**labels).set(throughput_diff)

    def record_operator_processing_time(self, operator_id: str, pipeline_id: str,
                                      operator_type: str, processing_time_us: float):
        """Record operator processing time"""
        # Gauge - for latest value and real-time monitoring
        self.operator_processing_time_latest.labels(
            operator_id=operator_id,
            pipeline_id=pipeline_id,
            operator_type=operator_type
        ).set(processing_time_us)

        # Histogram - for distribution, percentiles, and SLA monitoring
        self.operator_processing_time_histogram.labels(
            operator_id=operator_id,
            pipeline_id=pipeline_id,
            operator_type=operator_type
        ).observe(processing_time_us)

    def update_pipeline_status(self, pipeline_id: str, active_ports: int, active_operators: int):
        """Update pipeline status metrics"""
        self.pipeline_active_ports.labels(pipeline_id=pipeline_id).set(active_ports)
        self.pipeline_active_operators.labels(pipeline_id=pipeline_id).set(active_operators)

    def record_collection_duration(self, duration_seconds: float):
        """Record metrics collection duration"""
        self.metrics_collection_duration_seconds.observe(duration_seconds)

    def record_collection_error(self, error_type: str):
        """Record metrics collection error"""
        # Mark service as inactive if there are collection errors
        self.service_status.labels(service='metrics').set(0)
        if error_type in ["no_pipelines", "no_pipeline_data"]:
            return
        self.metrics_collection_errors_total.labels(error_type=error_type).inc()

    def update_pipeline_info(self, pipeline_info: dict[str, str]):
        """Update pipeline information"""
        self.pipeline_info.info(pipeline_info)

    def update_service_status(self, is_active: bool = True):
        """Update service status"""
        self.service_status.labels(service='metrics').set(1 if is_active else 0)
        current_time = time.time()
        uptime = current_time - self.start_time
        self.service_uptime_seconds.labels(service='metrics').set(uptime)
