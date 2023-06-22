from __future__ import annotations

from typing import TYPE_CHECKING, Generator, List, Optional

from scheduler.app.database.arangodb.interfaces.base import DBBase
from scheduler.app.database.orm import ORMFuzzer, ORMFuzzerState
from scheduler.app.database.abstract import IActiveFuzzers
from .utils import (
    maybe_already_exists,
    maybe_not_found,
    maybe_unknown_error,
)
from asyncio import Lock

if TYPE_CHECKING:
    from aioarangodb.collection import StandardCollection
    from aioarangodb.database import StandardDatabase
    from scheduler.app.settings import CollectionSettings
    from scheduler.app.database.arangodb.database import ArangoDB
    from aioarangodb.cursor import Cursor


class DBActiveFuzzers(DBBase, IActiveFuzzers):

    _col_active_fuzzers: StandardCollection
    _write_lock: Lock # TODO: 

    def __init__(
        self,
        db: ArangoDB,
        collections: CollectionSettings,
    ):
        self._col_active_fuzzers = db._db[collections.active_fuzzers]
        self._write_lock = Lock()
        super().__init__(db, collections)


    @maybe_unknown_error
    async def set(self, fuzzer: ORMFuzzer) -> None:
        async with self._write_lock:
            doc = fuzzer.dict(exclude={"id", "state"})
            doc["_key"] = fuzzer.id
            await self._col_active_fuzzers.insert(doc, overwrite=True)


    @maybe_unknown_error
    async def update(self, fuzzer: ORMFuzzer) -> None:
        async with self._write_lock:
            filters = {
                "_key": fuzzer.id, 
                "rev": fuzzer.rev, 
                "session_id": fuzzer.session_id
            }

            doc = fuzzer.dict(exclude={"id", "state"})
            doc["_key"] = fuzzer.id
            await self._col_active_fuzzers.update_match(filters, doc, merge=False)


    @maybe_unknown_error
    async def delete(self, fuzzer: ORMFuzzer) -> None:
        async with self._write_lock:
            filters = {
                "_key": fuzzer.id, 
                "rev": fuzzer.rev, 
                "session_id": fuzzer.session_id
            }
            await self._col_active_fuzzers.delete_match(filters)


    @maybe_unknown_error
    async def list(self, pool_id: Optional[str] = None):

        # fmt: off
        query, variables = """
            FOR fuzzer IN @@col_fuzzers
                <pool-filter>

                LET fuzzer_state = FIRST(
                    FOR state IN @@col_states
                        FILTER state._key == CONCAT(fuzzer._key, "_", fuzzer.rev)
                        LIMIT 1 RETURN state
                )

                RETURN MERGE(fuzzer, {
                    state: fuzzer_state,
                })
        """, {
            "@col_fuzzers": self._collections.active_fuzzers,
            "@col_states": self._collections.fuzzer_states,
        }
        # fmt: on

        if pool_id is not None:
            query = query.replace("<pool-filter>", "FILTER fuzzer.pool_id == @pool_id")
            variables["pool_id"] = pool_id
        else:
            query = query.replace("<pool-filter>", "")

        cursor: Cursor = await self._db._db.aql.execute(query, bind_vars=variables)

        async def async_iter():
            async for doc in cursor:
                doc["id"] = doc["_key"]
                fuzzer = ORMFuzzer(**doc)
                if fuzzer.state is not None:
                    fuzzer.state.restart()

                yield fuzzer

        return async_iter()


    @maybe_unknown_error
    async def list_pools(self):
        # fmt: off
        query, variables = """
            FOR fuzzer in @@col_fuzzers
                COLLECT pool_id = fuzzer.pool_id
                FILTER pool_id != null
                RETURN pool_id
        """, {
            "@col_fuzzers": self._collections.active_fuzzers,
        }
        # fmt: on

        cursor: Cursor = await self._db._db.aql.execute(query, bind_vars=variables)

        async def async_iter():
            async for doc in cursor:
                yield doc
        
        return async_iter()
