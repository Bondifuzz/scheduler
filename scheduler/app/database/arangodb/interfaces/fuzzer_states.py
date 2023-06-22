from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from scheduler.app.database.arangodb.interfaces.base import DBBase
from scheduler.app.database.orm import ORMFuzzer, ORMFuzzerState
from scheduler.app.database.abstract import IFuzzerStates
from .utils import (
    maybe_already_exists,
    maybe_not_found,
    maybe_unknown_error,
)

from aioarangodb.exceptions import DocumentUpdateError
from aioarangodb.errno import DOCUMENT_NOT_FOUND

from asyncio import Lock

if TYPE_CHECKING:
    from aioarangodb.collection import StandardCollection
    from aioarangodb.database import StandardDatabase
    from scheduler.app.settings import CollectionSettings
    from scheduler.app.database.arangodb.database import ArangoDB


class DBFuzzerStates(DBBase, IFuzzerStates):

    _col_fuzzer_states: StandardCollection
    _write_lock: Lock # TODO: 

    def __init__(
        self,
        db: ArangoDB,
        collections: CollectionSettings,
    ):
        self._col_fuzzer_states = db._db[collections.fuzzer_states]
        self._write_lock = Lock()
        super().__init__(db, collections)


    @maybe_unknown_error
    async def get_state(self, fuzzer: ORMFuzzer) -> Optional[ORMFuzzerState]:
        doc = await self._col_fuzzer_states.get(fuzzer.id + "_" + fuzzer.rev)
        if doc is None:
            return None

        state = ORMFuzzerState(**doc)
        state.restart()
        return state


    @maybe_unknown_error
    async def set_state(self, fuzzer: ORMFuzzer) -> None:
        async with self._write_lock:
            doc = fuzzer.state.dict()
            doc["_key"] = fuzzer.id + "_" + fuzzer.rev
            await self._col_fuzzer_states.insert(doc, overwrite=True)


    @maybe_unknown_error
    async def update_state(self, fuzzer: ORMFuzzer) -> None:
        async with self._write_lock:
            doc = fuzzer.state.dict()
            doc["_key"] = fuzzer.id + "_" + fuzzer.rev
            try:
                await self._col_fuzzer_states.update(doc, merge=False)
            except DocumentUpdateError as e:
                # ignore on missing
                if e.error_code != DOCUMENT_NOT_FOUND:
                    raise


    @maybe_unknown_error
    async def delete_state(self, fuzzer: ORMFuzzer) -> None:
        async with self._write_lock:
            key = fuzzer.id + "_" + fuzzer.rev
            await self._col_fuzzer_states.delete(key, ignore_missing=True)
