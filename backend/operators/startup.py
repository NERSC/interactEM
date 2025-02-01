import asyncio
import importlib
import inspect
import os
import sys
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from interactem.core.constants import (
    OPERATOR_CLASS_NAME,
    OPERATOR_ID_ENV_VAR,
    OPERATOR_RUN_LOCATION,
)
from interactem.core.logger import get_logger

logger = get_logger()


class Settings(BaseSettings):
    model_config: SettingsConfigDict = SettingsConfigDict(extra="ignore")
    OPERATOR_ID: str | None = None

    @model_validator(mode="after")
    def set_operator_id(self) -> "Settings":
        if not self.OPERATOR_ID:
            raise ValueError("No operator ID provided")
        return self


cfg = Settings(OPERATOR_ID=os.getenv(OPERATOR_ID_ENV_VAR))


async def run_operator(module_name: str):
    # Import user-created module (e.g. "run.py")
    module = importlib.import_module(module_name)

    # Find the first function that returns an instance of Operator
    operator_function = None
    for attr_name in dir(module):
        attr = getattr(module, attr_name)

        # Skip non-functions
        # TODO: could look at module Classes, for cases e.g. ImageDisplay
        if not inspect.isfunction(attr):
            continue

        # Operator functions will have a __wrapped__ key in the function
        # dictionary
        is_wrapped = attr.__dict__.get("__wrapped__", False)

        if is_wrapped is False:
            continue

        # look at the function's code object
        if OPERATOR_CLASS_NAME in str(attr.__code__.co_consts):
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
