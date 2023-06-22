from __future__ import annotations
from typing import TYPE_CHECKING, AsyncIterator, Dict, List, Optional

from abc import abstractmethod, ABCMeta

from scheduler.app.database.orm import ORMFuzzerState
from ..utils import testing_only

if TYPE_CHECKING:
    from ..settings import AppSettings
    from .orm import ORMFuzzer


class IActiveFuzzers(metaclass=ABCMeta):

    @abstractmethod
    async def set(self, fuzzer: ORMFuzzer) -> None:
        pass

    @abstractmethod
    async def update(self, fuzzer: ORMFuzzer) -> None:
        pass

    @abstractmethod
    async def delete(self, fuzzer: ORMFuzzer) -> None:
        pass

    @abstractmethod
    async def list(self, pool_id: Optional[str] = None) -> AsyncIterator[ORMFuzzer]:
        pass

    @abstractmethod
    async def list_pools(self) -> AsyncIterator[str]:
        pass


class IFuzzerStates(metaclass=ABCMeta):

    @abstractmethod
    async def get_state(self, fuzzer: ORMFuzzer) -> Optional[ORMFuzzerState]:
        pass

    @abstractmethod
    async def set_state(self, fuzzer: ORMFuzzer) -> None:
        pass

    @abstractmethod
    async def update_state(self, fuzzer: ORMFuzzer) -> None:
        pass

    @abstractmethod
    async def delete_state(self, fuzzer: ORMFuzzer) -> None:
        pass

class IUnsentMessages(metaclass=ABCMeta):

    """
    Used for saving/loading MQ unsent messages from database.
    """

    @abstractmethod
    async def save_unsent_messages(self, messages: Dict[str, list]):
        pass

    @abstractmethod
    async def load_unsent_messages(self) -> Dict[str, list]:
        pass

class IDatabase(metaclass=ABCMeta):

    """Used for managing database"""

    @classmethod
    @abstractmethod
    async def create(cls, settings: AppSettings):
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    @property
    @abstractmethod
    def active_fuzzers(self) -> IActiveFuzzers:
        pass

    @property
    @abstractmethod
    def fuzzer_states(self) -> IFuzzerStates:
        pass

    @property
    @abstractmethod
    def unsent_mq(self) -> IUnsentMessages:
        pass

    @abstractmethod
    @testing_only
    async def truncate_all_collections(self) -> None:
        pass
