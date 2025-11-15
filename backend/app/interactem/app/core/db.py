import uuid

from sqlmodel import Session, create_engine, select

from interactem.app import crud
from interactem.app.core.config import settings
from interactem.app.models import Pipeline, PipelineRevision, User, UserCreate
from interactem.core.logger import get_logger
from interactem.core.models.canonical import (
    CanonicalEdge,
    CanonicalInput,
    CanonicalOperator,
    CanonicalOutput,
    CanonicalPipelineData,
)
from interactem.core.models.spec import OperatorSpecParameter, ParameterSpecType

logger = get_logger()
engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28

HELLO_WORLD_PIPELINE_ID = uuid.UUID("12345678-9abc-def0-1234-567890abcdef")
IMAGE_DISPLAY_OP_ID = uuid.UUID("57d34f2e-f506-4d8c-8e0c-eaaa8ba800fb")
RANDOM_IMAGE_OP_ID = uuid.UUID("35ebbd89-3d5d-4387-a33b-570d263d98f7")
IMAGE_INPUT_PORT_ID = uuid.UUID("81607129-4ef2-4bb0-8bfe-be07e08ab1ed")
RANDOM_OUTPUT_PORT_ID = uuid.UUID("1d52ea77-fcbc-4831-96d5-02f83d8bf941")


def create_hello_world_pipeline(session: Session, user: User) -> None:
    """Create a hello world example pipeline if it doesn't already exist."""
    logger.info(
        f"Checking if hello world pipeline exists: {HELLO_WORLD_PIPELINE_ID}"
    )
    existing_pipeline = session.exec(
        select(Pipeline).where(Pipeline.id == HELLO_WORLD_PIPELINE_ID)
    ).first()
    if existing_pipeline:
        logger.info(
            f"Hello world pipeline already exists with ID: {HELLO_WORLD_PIPELINE_ID}"
        )
        return

    logger.info("Creating hello world example pipeline")

    # Create the operators using Pydantic models
    image_display_op = CanonicalOperator(
        id=IMAGE_DISPLAY_OP_ID,
        label="Image",
        description="Display an image",
        image="ghcr.io/nersc/interactem/image-display:latest",
        inputs=[IMAGE_INPUT_PORT_ID],
        outputs=[],
        parameters=None,
        tags=[],
        parallel_config=None,
        spec_id=uuid.UUID("12345678-0000-0002-0000-1234567890ac"),
    )

    random_image_op = CanonicalOperator(
        id=RANDOM_IMAGE_OP_ID,
        label="Random Image",
        description="Generates a random image",
        image="ghcr.io/nersc/interactem/random-image:latest",
        inputs=[],
        outputs=[RANDOM_OUTPUT_PORT_ID],
        parameters=[
            OperatorSpecParameter(
                name="width",
                label="Image width",
                description="The width of the image",
                type=ParameterSpecType.INTEGER,
                default="100",
                required=True,
            ),
            OperatorSpecParameter(
                name="height",
                label="Image height",
                description="The height of the image",
                type=ParameterSpecType.INTEGER,
                default="100",
                required=True,
            ),
            OperatorSpecParameter(
                name="interval",
                label="Interval",
                description="The interval at which to generate the image",
                type=ParameterSpecType.INTEGER,
                default="2",
                required=True,
            ),
        ],
        tags=[],
        parallel_config=None,
        spec_id=uuid.UUID("92345678-1234-1234-1234-1234567890ab"),
    )

    # Create the ports using proper Pydantic models
    image_input_port = CanonicalInput(
        id=IMAGE_INPUT_PORT_ID,
        canonical_operator_id=IMAGE_DISPLAY_OP_ID,
        portkey="81607129-4ef2-4bb0-8bfe-be07e08ab1ed",
    )

    random_output_port = CanonicalOutput(
        id=RANDOM_OUTPUT_PORT_ID,
        canonical_operator_id=RANDOM_IMAGE_OP_ID,
        portkey="1d52ea77-fcbc-4831-96d5-02f83d8bf941",
    )

    # Create the edge connecting the operators
    edge = CanonicalEdge(
        input_id=RANDOM_OUTPUT_PORT_ID,
        output_id=IMAGE_INPUT_PORT_ID,
    )

    # Create the complete pipeline data
    pipeline_data = CanonicalPipelineData(
        operators=[image_display_op, random_image_op],
        ports=[image_input_port, random_output_port],
        edges=[edge],
    )

    # Create the Pipeline record
    pipeline = Pipeline(
        id=HELLO_WORLD_PIPELINE_ID,
        owner_id=user.id,
        name="Hello World",
        data=pipeline_data.model_dump(mode="json"),
        current_revision_id=0,
    )
    session.add(pipeline)
    session.flush()

    # Create the initial PipelineRevision
    revision = PipelineRevision(
        pipeline_id=HELLO_WORLD_PIPELINE_ID,
        revision_id=0,
        data=pipeline_data.model_dump(mode="json"),
        positions=[
            {
                "canonical_operator_id": str(RANDOM_IMAGE_OP_ID),
                "x": -100.0,
                "y": 0.0,
            },
            {
                "canonical_operator_id": str(IMAGE_DISPLAY_OP_ID),
                "x": 100.0,
                "y": 0.0,
            },
        ],
    )
    session.add(revision)
    session.commit()

    logger.info(
        f"Successfully created hello world pipeline with ID: {HELLO_WORLD_PIPELINE_ID}"
    )


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # from interactem.app.core.engine import engine
    # This works because the models are already imported and registered from interactem.app.models
    # SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.username == settings.FIRST_SUPERUSER_USERNAME)
    ).first()
    if not user:
        user_in = UserCreate(
            username=settings.FIRST_SUPERUSER_USERNAME,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)

    create_hello_world_pipeline(session, user)
