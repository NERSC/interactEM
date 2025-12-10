"""
These constants are used throughout interactEM, mostly for NATS streams and buckets.
At top level are what we want to talk about (the streams), like status, metrics, and notifications.
We then define who we are talking about, like pipelines, agents, operators, and ports.
Underneath this level is typically the ID of the subject, like a pipeline ID, agent ID, operator ID, or port ID.

Later, we could sneak a user ID between the type and the ID, but we don't do that yet.

We should ideally keep these short, nats recommends <16 tokens (hierarchy levels) and <256 characters total.
ref: https://github.com/nats-io/nats.docs/blob/master/nats-concepts/subjects.md
"""

NATS_TIMEOUT_DEFAULT = 10

# Streams/buckets
BUCKET_STATUS = "stat"
BUCKET_STATUS_TTL = 30

STREAM_METRICS = "met"
SUBJECT_METRICS_ALL = f"{STREAM_METRICS}.>"
BUCKET_METRICS = STREAM_METRICS
BUCKET_METRICS_TTL = 30

STREAM_NOTIFICATIONS = "noti"
SUBJECT_NOTIFICATIONS_ALL = f"{STREAM_NOTIFICATIONS}.>"

STREAM_PARAMETERS = "par"
SUBJECT_PARAMETERS_ALL = f"{STREAM_PARAMETERS}.>"

STREAM_DEPLOYMENTS = "depl"
SUBJECT_DEPLOYMENTS_ALL = f"{STREAM_DEPLOYMENTS}.>"

STREAM_IMAGES = "img"
SUBJECT_IMAGES_ALL = f"{STREAM_IMAGES}.>"

STREAM_TABLES = "tbl"
SUBJECT_TABLES_ALL = f"{STREAM_TABLES}.>"

STREAM_LOGS = "log"
SUBJECT_LOGS_ALL = f"{STREAM_LOGS}.>"

STREAM_SFAPI = "sfapi"
SUBJECT_SFAPI_JOBS = f"{STREAM_SFAPI}.jobs"
SUBJECT_SFAPI_ALL = f"{STREAM_SFAPI}.>"

# Common
PIPELINES = "pipe"
OPERATORS = "op"
AGENTS = "agent"
PORTS = "port"
ERRORS = "err"
INFO = "info"
UPDATES = "upd"
TRIGGERS = "trig"
ASSIGNMENTS = "asgn"

# Pipelines
SUBJECT_PIPELINES_METRICS = f"{STREAM_METRICS}.{PIPELINES}"

# We will have subjects like:
# depl.pipe.<deployment_id>, depl.pipe.<deployment_id>.asgn, depl.pipe.<deployment_id>.upd
SUBJECT_PIPELINES_DEPLOYMENTS = f"{STREAM_DEPLOYMENTS}.{PIPELINES}"
SUBJECT_PIPELINES_DEPLOYMENTS_UPDATE = f"{SUBJECT_PIPELINES_DEPLOYMENTS}.{UPDATES}"

# Agents
# TODO: come back to agent errors/info when doing logging
SUBJECT_AGENTS_NOTIFICATIONS = f"{STREAM_NOTIFICATIONS}.{AGENTS}"
SUBJECT_AGENTS_NOTIFICATIONS_ERRORS = f"{SUBJECT_AGENTS_NOTIFICATIONS}.{ERRORS}"
SUBJECT_AGENTS_NOTIFICATIONS_INFO = f"{SUBJECT_AGENTS_NOTIFICATIONS}.{INFO}"
SUBJECT_AGENTS_DEPLOYMENTS = f"{STREAM_DEPLOYMENTS}.{AGENTS}"
SUBJECT_AGENTS_LOGS = f"{STREAM_LOGS}.{AGENTS}"

# Operators
SUBJECT_OPERATORS_PARAMETERS = f"{STREAM_PARAMETERS}.{OPERATORS}"
# we get operator parameters updates from the frontend, we use a different subject
# for the update channel
SUBJECT_OPERATORS_PARAMETERS_UPDATE = f"{SUBJECT_OPERATORS_PARAMETERS}.{UPDATES}"
# TODO: come back to operator errors/info when doing logging
SUBJECT_OPERATORS_NOTIFICATIONS_ERRORS = f"{STREAM_NOTIFICATIONS}.{OPERATORS}.{ERRORS}"
SUBJECT_OPERATORS_NOTIFICATIONS_INFO = f"{STREAM_NOTIFICATIONS}.{OPERATORS}.{INFO}"
SUBJECT_OPERATORS_METRICS = f"{STREAM_METRICS}.{OPERATORS}"
SUBJECT_OPERATORS_DEPLOYMENTS = f"{STREAM_DEPLOYMENTS}.{OPERATORS}"
SUBJECT_OPERATORS_TRIGGERS = f"{TRIGGERS}.{OPERATORS}"

# Logs - hierarchical structure: log.depl.{deployment_id}.op.{operator_id}
SUBJECT_LOGS_DEPLOYMENTS = f"{STREAM_LOGS}.depl"

# TODO: come back to notifications errors/info when doing logging
SUBJECT_NOTIFICATIONS_ERRORS = f"{STREAM_NOTIFICATIONS}.{ERRORS}"
SUBJECT_NOTIFICATIONS_INFO = f"{STREAM_NOTIFICATIONS}.{INFO}"

# Vector
SUBJECT_LOGS_VECTOR = f"{STREAM_LOGS}.vector"
MAX_LOGS_PER_SUBJECT = 10000

# Superfacility API
SFAPI_SERVICE_NAME = "sfapi-service"
SFAPI_GROUP_NAME = f"{STREAM_SFAPI}-micro"
SFAPI_STATUS_ENDPOINT = "status"

OPERATOR_ID_ENV_VAR = "INTERACTEM_AGENT_ID"
OPERATOR_CLASS_NAME = "Operator"
OPERATOR_RUN_LOCATION = "/app/run.py"

MOUNT_DIR = "/mnt"

PACKAGE_DIR_IN_CONTAINER = "/interactem"

# Vector log agent stuff
LOGS_DIR_IN_CONTAINER = f"{PACKAGE_DIR_IN_CONTAINER}/logs"
VECTOR_IMAGE = "docker.io/timberio/vector:0.50.0-alpine"

NATS_API_KEY_HEADER = "X-API-Key"
INTERACTEM_IMAGE_REGISTRY = "ghcr.io/nersc/interactem/"
