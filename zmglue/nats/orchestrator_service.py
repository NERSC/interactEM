import asyncio
import contextlib
import signal
from uuid import uuid4

from nats import micro
from nats.aio.client import Client as NATS
from pydantic import ValidationError

from zmglue.fixtures import PIPELINE
from zmglue.logger import get_logger
from zmglue.models import (
    CommBackend,
    PipelineMessage,
    URIConnectMessage,
    URIConnectResponseMessage,
    URILocation,
    URIUpdateMessage,
)
from zmglue.models.messages import PutPipelineNodeMessage
from zmglue.models.uri import URI
from zmglue.pipeline import Pipeline

logger = get_logger("orchestrator", "DEBUG")

DEFAULT_NATS_ADDRESS: str = "nats://localhost:4222"
DEFAULT_ORCHESTRATOR_URI = URI(
    id=uuid4(),
    hostname="localhost",
    location=URILocation.orchestrator,
    comm_backend=CommBackend.NATS,
    query={"address": [DEFAULT_NATS_ADDRESS]},
)


class Orchestrator:
    def __init__(self):
        self.nc = NATS()
        self.pipeline = Pipeline.from_pipeline(PIPELINE)
        self.quit_event = asyncio.Event()
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self):
        await self.nc.connect(servers=[DEFAULT_NATS_ADDRESS])

    async def handle_pipeline_request(self, msg: micro.Request):
        try:
            PipelineMessage.model_validate_json(msg.data())
        except ValidationError:
            # TODO: Correct error code/message
            await msg.respond_error(code=400, description="Invalid pipeline message.")
            return
        await msg.respond(
            PipelineMessage(pipeline=self.pipeline.to_json()).model_dump_json().encode()
        )

    async def handle_uri_update_request(self, msg: micro.Request):
        try:
            model = URIUpdateMessage.model_validate_json(msg.data())
        except ValidationError:
            # TODO: Correct error code/message
            await msg.respond_error(code=400, description="Invalid URI update message.")
            return
        logger.info(f"Received URI update request from {model.id}.")
        self.pipeline.update_uri(model)
        await msg.respond(msg.data())

    async def handle_uri_connect_request(self, msg: micro.Request):
        model = URIConnectMessage.model_validate_json(msg.data())
        uris = self.pipeline.get_connections(model)
        await msg.respond(
            URIConnectResponseMessage(connections=uris).model_dump_json().encode()
        )

    async def handle_put_pipeline_node(self, msg: micro.Request):
        try:
            model = PutPipelineNodeMessage.model_validate_json(msg.data())
        except ValidationError as e:
            # TODO: Correct error code/message
            await msg.respond_error(code=400, description=str(e))
            return
        self.pipeline.put_node(model)
        await msg.respond(msg.data())

    async def run(self):
        logger.info("Starting orchestrator...")
        self.loop = asyncio.get_event_loop()

        for sig in (signal.Signals.SIGINT, signal.Signals.SIGTERM):
            self.loop.add_signal_handler(sig, lambda *_: self.quit_event.set())
        async with contextlib.AsyncExitStack() as stack:

            logger.info("Connecting to NATS...")
            await self.nc.connect("nats://localhost:4222")
            logger.info("Connected to NATS.")
            stack.push_async_callback(self.nc.close)

            service = await stack.enter_async_context(
                micro.add_service(
                    self.nc,
                    name="orchestrator-service",
                    version="0.0.1",
                    description="Orchestrator service",
                )
            )
            logger.info("Orchestrator service created.")

            orchestrator = service.add_group("orchestrator")

            pipeline = orchestrator.add_group(name="pipeline")
            await pipeline.add_endpoint(
                name="get",
                handler=self.handle_pipeline_request,
            )
            await pipeline.add_endpoint(
                name="put",
                handler=self.handle_put_pipeline_node,
            )

            uri_grp = orchestrator.add_group("uri")
            await uri_grp.add_endpoint(
                name="get",
                handler=self.handle_uri_connect_request,
            )
            await uri_grp.add_endpoint(
                name="put",
                handler=self.handle_uri_update_request,
            )

            logger.info("Orchestrator running...")
            await self.quit_event.wait()
            logger.info("Orchestrator stopped.")

    def start(self):
        asyncio.run(self.run())
