from faststream.nats import JStream
from nats.js.api import RetentionPolicy, StreamConfig

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

PARAMETERS_STREAM_CONFIG = StreamConfig(
    name=STREAM_PARAMETERS,
    description="A stream for operator parameters.",
    subjects=[SUBJECT_PARAMETERS_ALL],
    # We only need the last value for each parameter
    max_msgs_per_subject=1,
)

IMAGES_STREAM_CONFIG = StreamConfig(
    name=STREAM_IMAGES,
    description="A stream for images.",
    subjects=[SUBJECT_IMAGES_ALL],
    max_msgs_per_subject=1,
)

METRICS_STREAM_CONFIG = StreamConfig(
    name=STREAM_METRICS,
    description="A stream for message metrics.",
    subjects=[f"{STREAM_METRICS}.>"],
    max_age=60,  # seconds
)

SFAPI_STREAM_CONFIG = StreamConfig(
    name=STREAM_SFAPI,
    description="A stream for messages to the SFAPI.",
    subjects=[SUBJECT_SFAPI_ALL],
)

NOTIFICATIONS_STREAM_CONFIG = StreamConfig(
    name=STREAM_NOTIFICATIONS,
    description="A stream for notifications.",
    subjects=[SUBJECT_NOTIFICATIONS_ALL],
    retention=RetentionPolicy.INTEREST,
)

NOTIFICATIONS_JSTREAM = JStream(
    name=STREAM_NOTIFICATIONS,
    description="A stream for notifications.",
    subjects=[SUBJECT_NOTIFICATIONS_ALL],
    retention=RetentionPolicy.INTEREST,
)

DEPLOYMENTS_STREAM_CONFIG = StreamConfig(
    name=STREAM_DEPLOYMENTS,
    description="A stream for deployments.",
    subjects=[SUBJECT_DEPLOYMENTS_ALL],
)

DEPLOYMENTS_JSTREAM = JStream(
    name=STREAM_DEPLOYMENTS,
    description="A stream for deployments.",
    subjects=[SUBJECT_DEPLOYMENTS_ALL],
)

TABLE_STREAM_CONFIG = StreamConfig(
    name=STREAM_TABLES,
    subjects=[SUBJECT_TABLES_ALL],
    description="A stream for tables.",
    retention=RetentionPolicy.LIMITS,
    max_msgs_per_subject=1,
)
