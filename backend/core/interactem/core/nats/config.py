from nats.js.api import RetentionPolicy, StreamConfig

from interactem.core.constants import (
    STREAM_AGENTS,
    STREAM_IMAGES,
    STREAM_METRICS,
    STREAM_NOTIFICATIONS,
    STREAM_OPERATORS,
    STREAM_PARAMETERS,
    STREAM_PIPELINES,
    STREAM_SFAPI,
)

PARAMETERS_STREAM_CONFIG = StreamConfig(
    name=STREAM_PARAMETERS,
    description="A stream for operator parameters.",
    subjects=[f"{STREAM_PARAMETERS}.>"],
)

PIPELINES_STREAM_CONFIG = StreamConfig(
    name=STREAM_PIPELINES,
    description="A stream for pipeline messages",
    subjects=[f"{STREAM_PIPELINES}.>"],
)

IMAGES_STREAM_CONFIG = StreamConfig(
    name=STREAM_IMAGES,
    description="A stream for images.",
    subjects=[f"{STREAM_IMAGES}.>"],
    max_msgs_per_subject=1,
)

METRICS_STREAM_CONFIG = StreamConfig(
    name=STREAM_METRICS,
    description="A stream for message metrics.",
    subjects=[f"{STREAM_METRICS}.>"],
    max_age=60,  # seconds
)

AGENTS_STREAM_CONFIG = StreamConfig(
    name=STREAM_AGENTS,
    description="A stream for messages to the agents.",
    subjects=[f"{STREAM_AGENTS}.>"],
)

SFAPI_STREAM_CONFIG = StreamConfig(
    name=STREAM_SFAPI,
    description="A stream for messages to the SFAPI.",
    subjects=[f"{STREAM_SFAPI}.>"],
)

NOTIFICATIONS_STREAM_CONFIG = StreamConfig(
    name=STREAM_NOTIFICATIONS,
    description="A stream for notifications.",
    subjects=[f"{STREAM_NOTIFICATIONS}.>"],
    retention=RetentionPolicy.INTEREST,
)

OPERATORS_STREAM_CONFIG = StreamConfig(
    name=STREAM_OPERATORS,
    description="A stream for messages for operators.",
    subjects=[f"{STREAM_OPERATORS}.>"],
)
