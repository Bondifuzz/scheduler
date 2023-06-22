from __future__ import annotations
from typing import TYPE_CHECKING

import logging
from abc import ABCMeta, abstractmethod
from asyncio import Task, Lock, Event

if TYPE_CHECKING:
    from mqtransport import MQApp
    from scheduler.app.database.orm import ORMFuzzer
    from scheduler.app.message_queue.instance import MQAppState
    from typing import Optional


class ScheduleEmptyError(Exception):
    pass


class SchedulerBase(metaclass=ABCMeta):
    _logger: logging.Logger

    @abstractmethod
    async def start_fuzzer(self, fuzzer: ORMFuzzer) -> None:
        pass

    @abstractmethod
    async def stop_fuzzer(self, fuzzer_id: str) -> None:
        pass

    @abstractmethod
    async def update_weight(self, fuzzer_id: str) -> None:
        pass

    @abstractmethod
    async def choose_next(self) -> Optional[ORMFuzzer]:
        pass
