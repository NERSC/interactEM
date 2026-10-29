from pathlib import Path
from typing import Any

import ncempy

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import DATA_DIRECTORY, operator

logger = get_logger()

# This adds a parameter for the raw data directory location
data_dir = Path(f"{DATA_DIRECTORY}/raw_data_dir")

@operator
def read_data_ncempy(
    inputs: BytesMessage | None, parameters: dict[str, Any], trigger=None
) -> BytesMessage | None:
    """Read and emit TEM data from a specified file when triggered."""
    if trigger is None:
        return None

    # Extract parameters
    directory = parameters.get("raw_data_dir", "/test_data")
    file = parameters.get("file", "test.emd")

    # Read data from disk
    logger.info("read_tem_data operator running...")

    logger.info(f"parameter directory: {directory}")
    logger.info(f"internal mount directory: {data_dir}")
    logger.info(f"file name: {file}")

    file_path = data_dir / Path(file)
    try:
        dd = ncempy.read(file_path)
        data = dd['data']
        logger.info(f'file data shape: {data.shape}')
    except Exception as e:
        logger.info(f"Problem loading file. Error: {e}")
        return None

    # Process and return result if the data was loaded successfully
    data_bytes = data.tobytes()
    header = MessageHeader(
        subject=MessageSubject.BYTES,
        meta={
            "shape": data.shape,
            "dtype": str(data.dtype),
        },
    )
    return BytesMessage(header=header, data=data_bytes)
