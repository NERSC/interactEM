from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING, Annotated

from faststream import Depends
from faststream.nats import NatsMessage
from sqlmodel import Session

from interactem.app.api.deps import get_db
from interactem.app.core.config import settings
from interactem.core.logger import get_logger

if TYPE_CHECKING:
    from fast_depends.dependencies import Depends

logger = get_logger()


class ApiKeyType(str, Enum):
    ORCHESTRATOR = "orchestrator"


API_KEY_MAP = {
    ApiKeyType.ORCHESTRATOR: settings.ORCHESTRATOR_API_KEY,
}


def create_api_key_verifier(api_key_type: ApiKeyType) -> Callable[[NatsMessage], bool]:
    """Creates a function to verify API keys based on the type provided."""

    def verify_api_key(msg: NatsMessage) -> bool:
        headers = msg.headers
        if not headers:
            raise ValueError("Message headers are required.")

        api_key = headers.get("X-API-Key")
        if not api_key:
            raise ValueError("X-API-Key header is required.")

        expected_key = API_KEY_MAP.get(api_key_type)
        if not expected_key:
            raise ValueError(f"No API key configured for type: {api_key_type}")

        if api_key != expected_key:
            raise ValueError(f"Invalid {api_key_type} API key")

        logger.info(f"{api_key_type} API key verified")
        return True

    return verify_api_key


def get_api_key_dependency(api_key_type: ApiKeyType) -> Depends:
    verifier = create_api_key_verifier(api_key_type)

    return Depends(verifier)


OrchestratorApiKeyDep = get_api_key_dependency(ApiKeyType.ORCHESTRATOR)
SessionDep = Annotated[Session, Depends(get_db)]
