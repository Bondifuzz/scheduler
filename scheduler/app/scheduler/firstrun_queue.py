
from __future__ import annotations
from asyncio import Lock
from typing import TYPE_CHECKING

import logging
from scheduler.app.database.abstract import IDatabase
from scheduler.app.message_queue.state import MQAppState

from scheduler.app.utils import get_unixtime

if TYPE_CHECKING:
    from scheduler.app.database.orm import ORMFuzzer
    from typing import Optional, List, Dict


class FirstRunQueue:

    _logger: logging.Logger
    _lock: Lock
    _queue: Dict[str, ORMFuzzer]

    def __init__(self, state: MQAppState, fuzzers: List[ORMFuzzer] = list()):
        self._logger = logging.getLogger("FirstRunQueue")
        self._lock = Lock()

        self._queue = {}
        for fuzzer in fuzzers:
            if not fuzzer.is_verified:
                self._queue[fuzzer.id] = fuzzer

    async def stop_fuzzer(self, id: str) -> None:
        async with self._lock:
            self._queue.pop(id, None)

    async def start_fuzzer(self, fuzzer: ORMFuzzer) -> None:
        async with self._lock:
            self._queue[fuzzer.id] = fuzzer

    async def choose_next(self) -> Optional[ORMFuzzer]:
        async with self._lock:
            for id in self._queue:
                fuzzer = self._queue[id]
                if not fuzzer.state.merge_running:
                    return fuzzer
            return None

