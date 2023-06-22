from __future__ import annotations
from typing import TYPE_CHECKING, Optional
import logging
from scheduler.app.database.arangodb.interfaces.fuzzer_states import DBFuzzerStates

from scheduler.app.utils import testing_only

from .initializer import ArangoDBInitializer

from .interfaces.unsent_mq import DBUnsentMessages
from .interfaces.active_fuzzers import DBActiveFuzzers
from ..abstract import IDatabase

if TYPE_CHECKING:
    from aioarangodb.database import StandardDatabase
    from aioarangodb.client import ArangoClient
    from scheduler.app.settings import AppSettings, CollectionSettings
    from ..abstract import IActiveFuzzers, IFuzzerStates, IUnsentMessages


class ArangoDB(IDatabase):

    _db_active_fuzzers: IActiveFuzzers
    _db_fuzzer_states: IFuzzerStates
    _db_unsent_mq: IUnsentMessages

    _logger: logging.Logger
    _collections: CollectionSettings
    _client: Optional[ArangoClient]
    _db: StandardDatabase
    _is_closed: bool

    @property
    def unsent_mq(self):
        return self._db_unsent_mq

    @property
    def active_fuzzers(self):
        return self._db_active_fuzzers
    
    @property
    def fuzzer_states(self):
        return self._db_fuzzer_states

    async def _init(self, settings: AppSettings):

        self._client = None
        self._is_closed = True
        self._logger = logging.getLogger("db")

        db_initializer = await ArangoDBInitializer.create(settings)
        await db_initializer.do_init()

        self._db = db_initializer.db
        client = db_initializer.client
        collections = db_initializer.collections

        self._db_active_fuzzers = DBActiveFuzzers(self, collections)
        self._db_fuzzer_states = DBFuzzerStates(self, collections)
        self._db_unsent_mq = DBUnsentMessages(self, collections)

        self._is_closed = False
        self._collections = collections
        self._client = client

    @staticmethod
    async def create(settings):
        _self = ArangoDB()
        await _self._init(settings)
        return _self

    @testing_only
    async def truncate_all_collections(self):
        self._logger.warning("Clearing all collections...")
        async with self._db.begin_batch_execution(return_result=False) as db:
            for col_name in [col["name"] for col in await self._db.collections()]:
                await db.collection(col_name).truncate()

    async def close(self):

        assert not self._is_closed, "Database connection has been already closed"
        
        if self._client:
            await self._client.close()
            self._client = None

        self._is_closed = True

    def __del__(self):
        if not self._is_closed:
            self._logger.error("Database connection has not been closed")
