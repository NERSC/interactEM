from typing import Any

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import operator

logger = get_logger()

@operator
def update_distiller_metadata(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    """Adds information about a scan to the Disitller metadata"""

    if not inputs:
        logger.warning("No input provided to the update_distiller_metadata operator.")
        return None

    # Extract parameters

    # TODO: Implement operator logic here
    logger.info("update_distiller_metadata operator running...")

    # Process input data
    # data = inputs.data

    # TODO: Process and return result

    return None
