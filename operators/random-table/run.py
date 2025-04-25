import pickle
import random
import time
from typing import Any

import pandas as pd

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import operator

logger = get_logger()


@operator
def random_table_generator(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    """
    Generates a dictionary containing two pandas DataFrames with random data
    and sends it pickled.
    """

    update_interval_param = parameters.get("update_interval", 3)
    update_interval = float(update_interval_param)
    logger.debug(f"Sleeping for {update_interval} seconds.")
    time.sleep(update_interval)

    data1 = {
        "ID": [f"A{i:03d}" for i in range(5)],
        "Value1": [random.randint(0, 100) for _ in range(5)],
        "Status": [random.choice(["Active", "Inactive", "Pending"]) for _ in range(5)],
        "Progress": [round(random.random(), 2) for _ in range(5)],
    }
    df_table1 = pd.DataFrame(data1)

    data2 = {
        "Category": [random.choice(["X", "Y", "Z"]) for _ in range(3)],
        "MetricA": [random.gauss(50, 15) for _ in range(3)],
        "MetricB": [random.uniform(1000, 2000) for _ in range(3)],
        "Timestamp": [
            pd.Timestamp.now() - pd.Timedelta(seconds=random.randint(0, 60))
            for _ in range(3)
        ],
    }
    df_table2 = pd.DataFrame(data2)
    # Convert Timestamp to string for better pickle/JSON compatibility if needed later
    df_table2["Timestamp"] = df_table2["Timestamp"].astype(str)

    output_data = {
        "random_table_1": df_table1,
        "random_table_2": df_table2,
    }
    logger.info("Generated random table data.")

    serialized_data = pickle.dumps(output_data)
    logger.debug(f"Serialized random data using pickle ({len(serialized_data)} bytes).")

    return BytesMessage(
        header=MessageHeader(subject=MessageSubject.BYTES),
        data=serialized_data,
    )
