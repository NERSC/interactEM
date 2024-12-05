import asyncio
import importlib
import inspect
import os
import sys
from pathlib import Path

from pydantic import ConfigDict, model_validator
from pydantic_settings import BaseSettings

from core.constants import OPERATOR_ID_ENV_VAR, OPERATOR_RUN_LOCATION, OPERATOR_TAG
from core.logger import get_logger

logger = get_logger()


class Settings(BaseSettings):
    model_config: ConfigDict = ConfigDict(extra="ignore")
    OPERATOR_ID: str | None = None

    @model_validator(mode="after")
    def set_operator_id(self) -> "Settings":
        if not self.OPERATOR_ID:
            raise ValueError("No operator ID provided")
        return self


cfg = Settings(OPERATOR_ID=os.getenv(OPERATOR_ID_ENV_VAR))


async def run_operator(module_name: str):
    module = importlib.import_module(module_name)

    # Find the first decorated operator
    operator_function = None
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if inspect.isfunction(attr) and getattr(attr, OPERATOR_TAG, False):
            operator_function = attr
            break

    if operator_function is None:
        logger.error("No operator found in the module.")
        return

    op_instance = operator_function()

    try:
        await op_instance.start()
    except KeyboardInterrupt:
        logger.info("Shutting down operator...")
    finally:
        print("Application terminated.")


def startup():
    module_path = Path(OPERATOR_RUN_LOCATION)
    module_name = module_path.stem

    sys.path.insert(0, str(module_path.parent))
    asyncio.run(run_operator(module_name))


if __name__ == "__main__":
    startup()
