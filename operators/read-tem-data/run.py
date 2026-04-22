import time
from pathlib import Path
from typing import Any

import ncempy
import numpy as np

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import DATA_DIRECTORY, operator

logger = get_logger()

# This adds a parameter for the raw data directory location
data_dir = Path(f"{DATA_DIRECTORY}/raw_data_dir")

@operator
def read_data_ncempy(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    """This reads data from disk and sends it on."""

    # This operator does not require inputs

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

    # Send the data every 3 seonds
    # TODO: Use trigger instead of time.sleep to control when data is sent
    time.sleep(3.0)

    # Process and return result if the data was loaded successfully
    data_bytes = data.tobytes()
    header = MessageHeader(subject=MessageSubject.BYTES, meta={'shape': data.shape, 'dtype': str(data.dtype)})
    return BytesMessage(header=header, data=data_bytes)
