from faststream.nats import JStream
from nats.js.api import RetentionPolicy, StorageType, StreamConfig

from interactem.core.constants import (
    STREAM_DEPLOYMENTS,
    STREAM_IMAGES,
    STREAM_METRICS,
    STREAM_NOTIFICATIONS,
    STREAM_PARAMETERS,
    STREAM_SFAPI,
    STREAM_TABLES,
    SUBJECT_DEPLOYMENTS_ALL,
    SUBJECT_IMAGES_ALL,
    SUBJECT_NOTIFICATIONS_ALL,
    SUBJECT_PARAMETERS_ALL,
    SUBJECT_SFAPI_ALL,
    SUBJECT_TABLES_ALL,
)

ALL_STORAGE_TYPE = StorageType.MEMORY

PARAMETERS_STREAM_CONFIG = StreamConfig(
    name=STREAM_PARAMETERS,
    description="A stream for operator parameters.",
    subjects=[SUBJECT_PARAMETERS_ALL],
    # We only need the last value for each parameter
    max_msgs_per_subject=1,
    storage=ALL_STORAGE_TYPE,
)

IMAGES_STREAM_CONFIG = StreamConfig(
    name=STREAM_IMAGES,
    description="A stream for images.",
    subjects=[SUBJECT_IMAGES_ALL],
    max_msgs_per_subject=1,
    storage=ALL_STORAGE_TYPE,
)

METRICS_STREAM_CONFIG = StreamConfig(
    name=STREAM_METRICS,
    description="A stream for message metrics.",
    subjects=[f"{STREAM_METRICS}.>"],
    max_age=60,  # seconds
    storage=ALL_STORAGE_TYPE,
)

SFAPI_STREAM_CONFIG = StreamConfig(
    name=STREAM_SFAPI,
    description="A stream for messages to the SFAPI.",
    subjects=[SUBJECT_SFAPI_ALL],
    storage=ALL_STORAGE_TYPE,
)

NOTIFICATIONS_STREAM_CONFIG = StreamConfig(
    name=STREAM_NOTIFICATIONS,
    description="A stream for notifications.",
    subjects=[SUBJECT_NOTIFICATIONS_ALL],
    retention=RetentionPolicy.INTEREST,
    storage=ALL_STORAGE_TYPE,
)

NOTIFICATIONS_JSTREAM = JStream(
    name=STREAM_NOTIFICATIONS,
    description="A stream for notifications.",
    subjects=[SUBJECT_NOTIFICATIONS_ALL],
    retention=RetentionPolicy.INTEREST,
    storage=ALL_STORAGE_TYPE,
)

DEPLOYMENTS_STREAM_CONFIG = StreamConfig(
    name=STREAM_DEPLOYMENTS,
    description="A stream for deployments.",
    subjects=[SUBJECT_DEPLOYMENTS_ALL],
    storage=ALL_STORAGE_TYPE,
)

DEPLOYMENTS_JSTREAM = JStream(
    name=STREAM_DEPLOYMENTS,
    description="A stream for deployments.",
    subjects=[SUBJECT_DEPLOYMENTS_ALL],
    storage=ALL_STORAGE_TYPE,
)

TABLE_STREAM_CONFIG = StreamConfig(
    name=STREAM_TABLES,
    subjects=[SUBJECT_TABLES_ALL],
    description="A stream for tables.",
    retention=RetentionPolicy.LIMITS,
    max_msgs_per_subject=1,
    storage=ALL_STORAGE_TYPE,
)
