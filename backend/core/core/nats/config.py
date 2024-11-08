from nats.js.api import (
    StreamConfig,
)

from core.constants import (
    STREAM_AGENTS,
    STREAM_IMAGES,
    STREAM_METRICS,
    STREAM_OPERATORS,
    STREAM_PARAMETERS,
    STREAM_PIPELINES,
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
)

AGENTS_STREAM_CONFIG = StreamConfig(
    name=STREAM_AGENTS,
    description="A stream for messages to the agents.",
    subjects=[f"{STREAM_AGENTS}.>"],
)

OPERATORS_STREAM_CONFIG = StreamConfig(
    name=STREAM_OPERATORS,
    description="A stream for messages for operators.",
    subjects=[f"{STREAM_OPERATORS}.>"],
)
