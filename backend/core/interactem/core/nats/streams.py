"""Stream configuration definitions for NATS JetStream."""

from faststream.nats import JStream
from nats.js.api import RetentionPolicy, StreamConfig

from interactem.core.constants import (
    MAX_LOGS_PER_SUBJECT,
    STREAM_DEPLOYMENTS,
    STREAM_IMAGES,
    STREAM_LOGS,
    STREAM_METRICS,
    STREAM_NOTIFICATIONS,
    STREAM_PARAMETERS,
    STREAM_SFAPI,
    STREAM_TABLES,
    SUBJECT_DEPLOYMENTS_ALL,
    SUBJECT_IMAGES_ALL,
    SUBJECT_LOGS_ALL,
    SUBJECT_NOTIFICATIONS_ALL,
    SUBJECT_PARAMETERS_ALL,
    SUBJECT_SFAPI_ALL,
    SUBJECT_TABLES_ALL,
)

from .storage import cfg

_storage = cfg.NATS_STREAM_STORAGE_TYPE

PARAMETERS_STREAM_CONFIG = StreamConfig(
    name=STREAM_PARAMETERS,
    description="A stream for operator parameters.",
    subjects=[SUBJECT_PARAMETERS_ALL],
    max_msgs_per_subject=1,
    storage=_storage,
)

PARAMETERS_JSTREAM = JStream(
    name=STREAM_PARAMETERS,
    description="A stream for operator parameters.",
    subjects=[SUBJECT_PARAMETERS_ALL],
    max_msgs_per_subject=1,
    storage=_storage,
)

IMAGES_STREAM_CONFIG = StreamConfig(
    name=STREAM_IMAGES,
    description="A stream for images.",
    subjects=[SUBJECT_IMAGES_ALL],
    max_msgs_per_subject=1,
    storage=_storage,
)

METRICS_STREAM_CONFIG = StreamConfig(
    name=STREAM_METRICS,
    description="A stream for message metrics.",
    subjects=[f"{STREAM_METRICS}.>"],
    max_age=60,
    storage=_storage,
)

SFAPI_STREAM_CONFIG = StreamConfig(
    name=STREAM_SFAPI,
    description="A stream for messages to the SFAPI.",
    subjects=[SUBJECT_SFAPI_ALL],
    storage=_storage,
)

NOTIFICATIONS_STREAM_CONFIG = StreamConfig(
    name=STREAM_NOTIFICATIONS,
    description="A stream for notifications.",
    subjects=[SUBJECT_NOTIFICATIONS_ALL],
    retention=RetentionPolicy.INTEREST,
    storage=_storage,
)

NOTIFICATIONS_JSTREAM = JStream(
    name=STREAM_NOTIFICATIONS,
    description="A stream for notifications.",
    subjects=[SUBJECT_NOTIFICATIONS_ALL],
    retention=RetentionPolicy.INTEREST,
    storage=_storage,
)

DEPLOYMENTS_STREAM_CONFIG = StreamConfig(
    name=STREAM_DEPLOYMENTS,
    description="A stream for deployments.",
    subjects=[SUBJECT_DEPLOYMENTS_ALL],
    storage=_storage,
)

DEPLOYMENTS_JSTREAM = JStream(
    name=STREAM_DEPLOYMENTS,
    description="A stream for deployments.",
    subjects=[SUBJECT_DEPLOYMENTS_ALL],
    storage=_storage,
)

TABLE_STREAM_CONFIG = StreamConfig(
    name=STREAM_TABLES,
    subjects=[SUBJECT_TABLES_ALL],
    description="A stream for tables.",
    retention=RetentionPolicy.LIMITS,
    max_msgs_per_subject=1,
    storage=_storage,
)

LOGS_STREAM_CONFIG = StreamConfig(
    name=STREAM_LOGS,
    subjects=[SUBJECT_LOGS_ALL],
    description="A stream for logs.",
    retention=RetentionPolicy.LIMITS,
    max_msgs_per_subject=MAX_LOGS_PER_SUBJECT,
    max_age=3600 * 24 * 7,
    storage=_storage,
)
