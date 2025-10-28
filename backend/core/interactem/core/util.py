import asyncio
import sys
from collections.abc import Coroutine

if sys.version_info >= (3, 11):
    from builtins import BaseExceptionGroup
else:
    from exceptiongroup import BaseExceptionGroup

__all__ = ["BaseExceptionGroup", "create_task_with_ref"]

def create_task_with_ref(task_refs: set[asyncio.Task], coro: Coroutine) -> asyncio.Task:
    task = asyncio.create_task(coro)
    task_refs.add(task)
    task.add_done_callback(task_refs.discard)  # Clean up after completion
    return task
