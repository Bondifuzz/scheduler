import asyncio
from contextlib import asynccontextmanager, suppress
from logging import getLogger
from typing import Dict, Optional

from mqtransport import MQApp

from scheduler.app.database.orm import ORMFuzzer
from scheduler.app.message_queue.state import MQAppState
from scheduler.app.models import AgentOutput, AgentMode
from scheduler.app.pool.rwlock import RWLock
from .fuzzer_pool import FuzzerPool

from . import agent_errors

class PoolManager: # PoolRegistry

    _state: MQAppState
    _pools: Dict[str, FuzzerPool]
    _pool_locks: Dict[str, asyncio.Lock]
    _lock: RWLock

    def __init__(self, state: MQAppState) -> None:
        self._state = state
        self._pools = dict()
        self._pool_locks = dict()
        self._lock = RWLock()
        self._logger = getLogger("pool_manager")

    @staticmethod
    async def create(mq_app: MQApp):
        state: MQAppState = mq_app.state
        self = PoolManager(state)
        async for pool_id in await state.db.active_fuzzers.list_pools():
            self._pools[pool_id] = await FuzzerPool.create(pool_id, state, True)
            self._pool_locks[pool_id] = asyncio.Lock()
        
        return self

    async def close(self):
        async with self._lock.w_locked():
            for pool_id in list(self._pools.keys()):
                pool = self._pools.pop(pool_id)
                await pool.close()
                self._pool_locks.pop(pool_id, None)

            self._lock = None # TODO: 
            self._state = None
            self._pools = None
            self._pool_locks = None

    
    @asynccontextmanager
    async def lock_pool(self, pool_id: str):
        async with self._lock.r_locked():
            if pool_id not in self._pool_locks:
                self._pool_locks[pool_id] = asyncio.Lock()
            pool_lock = self._pool_locks[pool_id]
            
            try:
                await pool_lock.acquire()
                yield
            finally:
                pool_lock.release()


    async def clean_loop(self):
        while True:
            async with self._lock.w_locked():
                for pool_id in list(self._pools.keys()):
                    pool = self._pools[pool_id]
                    if pool is not None and pool.is_empty():
                        with suppress(Exception):
                            await pool.close()
                        pool = None
                    
                    if pool is None:
                        self._pools.pop(pool_id, None)
                        self._pool_locks.pop(pool_id, None)

            await asyncio.sleep(1 * 60)


    async def start_fuzzer(self, pool_id: str, fuzzer: ORMFuzzer):
        async with self.lock_pool(pool_id):
            if pool_id not in self._pools:
                self._pools[pool_id] = await FuzzerPool.create(pool_id, self._state)
            
            await self._pools[pool_id].start_fuzzer(fuzzer)


    async def update_fuzzer(
        self,
        pool_id: str,
        id: str,
        rev: str,
        cpu_usage: int,
        ram_usage: int,
        tmpfs_size: int,
    ):
        async with self.lock_pool(pool_id):
            if pool_id not in self._pools:
                raise Exception("PoolNotFoundError") # TODO:

            await self._pools[pool_id].update_fuzzer(
                id=id,
                rev=rev,
                cpu_usage=cpu_usage,
                ram_usage=ram_usage,
                tmpfs_size=tmpfs_size,
            )


    async def stop_fuzzer(self, pool_id: str, id: str, rev: str):
        async with self.lock_pool(pool_id):
            if pool_id not in self._pools:
                return

            await self._pools[pool_id].stop_fuzzer(
                id=id,
                rev=rev,
            )


    async def stop_all_fuzzers(self, pool_id: str):
        async with self.lock_pool(pool_id):
            if pool_id not in self._pools:
                return

            await self._pools[pool_id].stop_all_fuzzers()


    async def fuzzer_run_result(
        self,
        pool_id: str,
        id: str,
        rev: str,

        session_id: str,
        agent_mode: AgentMode,

        start_time: str,
        finish_time: str,
        result: Optional[AgentOutput],
    ):

        if result.status.code != agent_errors.E_SUCCESS:
            self._logger.debug("Fuzzer exited with error:")
            self._logger.debug(result.status)

        async with self.lock_pool(pool_id):
            if pool_id not in self._pools:
                return
            
            await self._pools[pool_id].fuzzer_run_result(
                id=id,
                rev=rev,

                session_id=session_id,
                agent_mode=agent_mode,
                
                start_time=start_time,
                finish_time=finish_time,
                result=result,
            )

    async def pod_finished(
        self,
        pool_id: str,
        id: str,
        rev: str,
        session_id: str,
        agent_mode: AgentMode,
        success: bool,
    ):
        async with self.lock_pool(pool_id):
            if pool_id not in self._pools:
                return
            
            await self._pools[pool_id].pod_finished(
                id=id,
                rev=rev,
                session_id=session_id,
                agent_mode=agent_mode,
                success=success,
            )
        pass


