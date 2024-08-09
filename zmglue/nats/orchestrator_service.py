import asyncio
import contextlib
import signal
from uuid import uuid4

import nats
import nats.micro
from nats.aio.client import Client as NATSClient
from nats.micro.request import Request
from nats.micro.service import GroupConfig, Service, ServiceConfig
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
        self.nc: NATSClient | None = None
        self.pipeline = Pipeline.from_pipeline(PIPELINE)
        self.quit_event = asyncio.Event()
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self):
        await self.nc.connect(servers=[DEFAULT_NATS_ADDRESS])

    async def handle_pipeline_request(self, msg: Request):
        try:
            PipelineMessage.model_validate_json(msg.data)
        except ValidationError:
            # TODO: Correct error code/message
            await msg.respond_error(code="400", description="Invalid pipeline message.")
            return
        await msg.respond(
            PipelineMessage(pipeline=self.pipeline.to_json()).model_dump_json().encode()
        )

    async def handle_uri_update_request(self, msg: Request):
        try:
            model = URIUpdateMessage.model_validate_json(msg.data)
        except ValidationError:
            # TODO: Correct error code/message
            await msg.respond_error(
                code="400", description="Invalid URI update message."
            )
            return
        logger.info(f"Received URI update request from {model.id}.")
        self.pipeline.update_uri(model)
        await msg.respond(msg.data)

    async def handle_uri_connect_request(self, msg: Request):
        model = URIConnectMessage.model_validate_json(msg.data)
        uris = self.pipeline.get_connections(model)
        await msg.respond(
            URIConnectResponseMessage(connections=uris).model_dump_json().encode()
        )

    async def handle_put_pipeline_node(self, msg: Request):
        try:
            model = PutPipelineNodeMessage.model_validate_json(msg.data)
        except ValidationError as e:
            # TODO: Correct error code/message
            await msg.respond_error(code="400", description=str(e))
            return
        self.pipeline.put_node(model)
        await msg.respond(msg.data)

    async def run(self):
        logger.info("Starting orchestrator...")
        self.loop = asyncio.get_event_loop()

        for sig in (signal.Signals.SIGINT, signal.Signals.SIGTERM):
            self.loop.add_signal_handler(sig, lambda *_: self.quit_event.set())
        async with contextlib.AsyncExitStack() as stack:
            logger.info("Connecting to NATS...")
            connect_address = "nats://localhost:4222"
            self.nc = await stack.enter_async_context(
                await nats.connect(connect_address)
            )
            logger.info(f"Connected to NATS at {connect_address}")
            stack.push_async_callback(self.nc.close)
            service: Service = await stack.enter_async_context(
                await nats.micro.add_service(
                    self.nc,
                    config=ServiceConfig(
                        name="orchestrator-service",
                        version="0.0.1",
                        description="Orchestrator service",
                    ),
                )
            )
            logger.info("Orchestrator service created.")

            orchestrator = service.add_group(GroupConfig(name="orchestrator"))
            logger.info("Orchestrator group created.")

            pipeline = orchestrator.add_group(GroupConfig(name="pipeline"))
            logger.info("orchestrator.pipeline group created.")
            await pipeline.add_endpoint(
                name="get",
                handler=self.handle_pipeline_request,
            )
            logger.info("orchestrator.pipeline.get endpoint created.")
            await pipeline.add_endpoint(
                name="put",
                handler=self.handle_put_pipeline_node,
            )
            logger.info("orchestrator.pipeline.put endpoint created.")

            uri_grp = orchestrator.add_group(GroupConfig(name="uri"))
            logger.info("orchestrator.uri group created.")
            await uri_grp.add_endpoint(
                name="get",
                handler=self.handle_uri_connect_request,
            )
            logger.info("orchestrator.uri.get endpoint created.")
            await uri_grp.add_endpoint(
                name="put",
                handler=self.handle_uri_update_request,
            )
            logger.info("orchestrator.uri.put endpoint created.")

            logger.info("Orchestrator running...")
            await self.quit_event.wait()
            logger.info("Orchestrator stopped.")

    def start(self):
        asyncio.run(self.run())
