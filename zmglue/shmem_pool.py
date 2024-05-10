from collections import deque
from multiprocessing.shared_memory import SharedMemory

from pydantic import BaseModel


class ShmemItem(BaseModel):
    name: str
    size: int
    refcount: int = 0


class ShmemPool:
    def __init__(self, max_pool_size: int = 1024 * 1024 * 1024):  # Default max size 1GB
        self._pool: dict[str, ShmemItem] = {}
        self._max_pool_size = max_pool_size
        self._pool_size = 0
        self._available: deque[str] = deque()
        self._used: deque[str] = deque()

    def _create_shmem(self, size: int) -> SharedMemory | None:
        popped: list[str] = []
        while self._available:
            name = self._available[0]
            item = self._pool[name]
            if item.size >= size and item.refcount == 0:
                item.refcount += 1
                self._available.popleft()
                return SharedMemory(create=False, name=name)
            popped.append(self._available.popleft())

        popped.reverse()
        self._available.extend(popped)

        if self._pool_size + size <= self._max_pool_size:
            shmem = SharedMemory(create=True, size=size)
            self._pool_size += shmem.size
            return shmem
        else:
            raise MemoryError("Not enough pool space to create new shared memory")

    def get_shmem(self, size: int) -> SharedMemory:
        shmem = self._create_shmem(size)
        if shmem:
            name = shmem.name
            if name not in self._pool:
                self._used.append(name)
                self._pool[name] = ShmemItem(name=name, refcount=1, size=size)
            return shmem
        else:
            raise Exception("Failed to allocate shared memory")

    def release_shmem(self, name: str) -> None:
        if name in self._pool:
            item = self._pool[name]
            item.refcount -= 1
            if item.refcount == 0:
                # Add to available queue for reuse
                self._available.append(name)

    def cleanup_unused_memory(self):
        while self._available:
            name = self._available.popleft()
            self._delete_shmem(name)

    def _delete_shmem(self, name: str) -> None:
        item = self._pool.pop(name, None)
        if item:
            shmem = SharedMemory(create=False, name=item.name)
            shmem.close()
            shmem.unlink()
            self._pool_size -= item.size

    def current_pool_size(self) -> int:
        return self._pool_size
