from types import TracebackType

import anyio
from faststream import BaseMiddleware
from faststream.exceptions import IgnoredException
from faststream.nats import NatsPublishCommand
from faststream.nats.publisher.usecase import LogicPublisher

from interactem.core.logger import get_logger
from interactem.core.models.base import IdType

from .constants import (
    DEPLOYMENT_ID_CTX_NAME,
    ERROR_PUBLISHER_CTX_NAME,
    ORCHESTRATOR_STATE_CTX_NAME,
)
from .state import OrchestratorState

logger = get_logger()


# Use ignored exceptions to avoid logging backtraces when we don't need them
class PipelineRunException(IgnoredException):
    message: str

    def __str__(self) -> str:
        return self.message


class CyclicDependenciesError(PipelineRunException):
    message = "Cyclic dependencies in pipeline."


class NoAgentsError(PipelineRunException):
    message = "No agents available."

class InvalidPipelineError(PipelineRunException):
    message = "Pipeline cannot be assigned: invalid pipeline."


class UnassignableOperatorsError(PipelineRunException):
    message = "Pipeline cannot be assigned: unassignable operators."


class NetworkPreferenceError(PipelineRunException):
    message = "Network preference violations. Check networks on operator definitions."


class PipelineExceptionMiddleware(BaseMiddleware[NatsPublishCommand]):
    """Logs handled pipeline exceptions while allowing proper message rejection.

    The exception still propagates to AcknowledgementMiddleware since we leave
    the return False, and we will NACK/REJECT the message based on
    the broker's ack_policy setting.
    """

    async def after_processed(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: TracebackType | None = None,
    ) -> bool | None:
        if exc_type is None:
            return await super().after_processed(exc_type, exc_val, exc_tb)
        error_pub: LogicPublisher = self.context.get(ERROR_PUBLISHER_CTX_NAME)
        deployment_id: IdType = self.context.get_local(DEPLOYMENT_ID_CTX_NAME)
        state: OrchestratorState = self.context.get(ORCHESTRATOR_STATE_CTX_NAME)
        sm = await state.get_deployment_sm(deployment_id)
        if issubclass(exc_type, PipelineRunException):
            # we get here if our pipeline handling failed, due to lack of agents
            # or invalid pipeline, or whatever else is under PipelineRunException
            msg = exc_type.message
            logger.error(f"Pipeline deployment run failed: {msg}")
            async with anyio.create_task_group() as tg:
                tg.start_soon(error_pub.publish, msg)
                tg.start_soon(sm.start_failure)

            # Return False to let exception propagate and be properly NACKed/REJECTed
            return False

        # we let other exceptions propagate as usual
        return await super().after_processed(exc_type, exc_val, exc_tb)
