from typing import Any

from pathlib import Path
import time

import ncempy
import numpy as np

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import operator, DATA_DIRECTORY

logger = get_logger()

# This adds a parameter for the raw data directory location
data_dir = Path(f"{DATA_DIRECTORY}/raw_data_dir")

@operator
def read_data_pae(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    """This reads data from disk and sends it on."""

    # This operator does not require inputs

    # Extract parameters
    directory = parameters.get("directory", "/test_data")
    file = parameters.get("file", "test.emd")
    # mount_dir = parameters.get("mount_dir", "~")

    # TODO: Implement operator logic here
    logger.info("read_tem_data operator running...")
    
    logger.info(f'directory: {directory}')
    logger.info(f'mount directory: {data_dir}')
    logger.info(f'file: {file}')
    # file_path = Path(directory) / Path(file)
    file_path = data_dir / Path(file)
    try:
        dd = ncempy.read(file_path)
        data = dd['data']
        logger.info(f'file data shape: {data.shape}')
    except:
        data = np.zeros((100, 100), dtype=np.uint8)
        logger.info('Problem loading file. Using zeros array.')
    time.sleep(3.0)
    
    # TODO: Process and return result
    data_bytes = data.tobytes()
    header = MessageHeader(subject=MessageSubject.BYTES, meta={'shape':data.shape, 'dtype':str(data.dtype)})
    return BytesMessage(header=header, data=data_bytes)
