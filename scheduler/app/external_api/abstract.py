from __future__ import annotations
from typing import TYPE_CHECKING

from abc import abstractmethod, ABCMeta

if TYPE_CHECKING:
    from ..settings import AppSettings
    from scheduler.app.database.orm import ORMFuzzer
    from scheduler.app.models import AgentMode
    from .models import StarterRunFuzzerResult


class APIBase(metaclass=ABCMeta):

    @abstractmethod
    async def close(self):
        pass


class IStarterAPI(APIBase):

    """Communication with Jira reporter"""

    @abstractmethod
    async def run_fuzzer(self, fuzzer: ORMFuzzer, agent_mode: AgentMode) -> StarterRunFuzzerResult:
        pass

    @abstractmethod
    async def stop_fuzzer(self, pool_id: str, fuzzer_id: str) -> None:
        pass

    @abstractmethod
    async def stop_all_fuzzers(self, pool_id: str) -> None:
        pass


class IExternalAPI(metaclass=ABCMeta):

    """Used for managing database"""

    @staticmethod
    @abstractmethod
    async def create(settings: AppSettings):
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    @property
    @abstractmethod
    def starter(self) -> IStarterAPI:
        pass
