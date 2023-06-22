from __future__ import annotations
from typing import TYPE_CHECKING

from contextlib import suppress
import asyncio
import logging

from datetime import datetime

from mqtransport import MQApp

from scheduler.app.external_api.models import StarterRunFuzzerResult
from . import agent_errors
from . import services

from scheduler.app.database.orm import ORMEngineID, ORMFuzzerState
from scheduler.app.models import AgentOutput, AgentMode, SchedulerError, StatisticsAFL, StatisticsBase, StatisticsLibFuzzer
from scheduler.app.scheduler.firstrun_queue import FirstRunQueue
from scheduler.app.scheduler.distance_scheduler import DistanceScheduler


if TYPE_CHECKING:
    from typing import Dict, Optional
    from scheduler.app.settings import AppSettings
    from scheduler.app.database.orm import ORMFuzzer
    from scheduler.app.message_queue.state import MQAppState
    from scheduler.app.models import Status


class FuzzerPool:
    pool_id: str
    firstrun_queue: FirstRunQueue
    weight_queue: DistanceScheduler
    
    _fuzzers: Dict[str, ORMFuzzer]
    _next_run: Optional[ORMFuzzer] = None

    _state: MQAppState
    _settings: AppSettings
    _lock: asyncio.Lock
    _logger: logging.Logger

    api_gateway: services.ApiGateway
    starter: services.Starter

    _run_event: asyncio.Event

    async def _init(self, pool_id: str, state: MQAppState, load_db: bool):
        self.pool_id = pool_id
        self.firstrun_queue = FirstRunQueue(state)
        self.weight_queue = DistanceScheduler(state)

        self.api_gateway = services.ApiGateway(state, state.external_api)
        self.starter = services.Starter(state, state.external_api)

        self._fuzzers = dict()

        self._state = state
        self._settings = state.settings
        self._lock = asyncio.Lock()
        self._logger = logging.getLogger("FuzzerPool")
        self._closed = False

        if load_db:
            async for fuzzer in await state.db.active_fuzzers.list(pool_id):
                self._fuzzers[fuzzer.id] = fuzzer

                if fuzzer.state is None:
                    fuzzer.state = ORMFuzzerState.default(state.settings)
                    await state.db.fuzzer_states.set_state(fuzzer)
                
                if fuzzer.state.weight <= 0:
                    await self._stop_fuzzer_internal(fuzzer.id)
                    await self.api_gateway.mq_fuzzer_stopped(
                        fuzzer.id, fuzzer.rev,
                        SchedulerError.ZeroWeight,
                    )

                else:
                    if not fuzzer.is_verified:
                        await self.firstrun_queue.start_fuzzer(fuzzer)
                    else:
                        await self.weight_queue.start_fuzzer(fuzzer)

        loop = asyncio.get_event_loop()
        self._loop_task = loop.create_task(self._run_loop())
        self._run_event = asyncio.Event()
        self._run_event.set()


    def is_empty(self):
        return len(self._fuzzers) == 0

    
    @staticmethod
    async def create(pool_id: str, state: MQAppState, load_db: bool = False):
        self = FuzzerPool()
        await self._init(pool_id, state, load_db)
        return self


    async def close(self):
        async with self._lock:
            self._closed = True
            self._loop_task.cancel()
            for fuzz_id in list(self._fuzzers.keys()):
                fuzzer = self._fuzzers.pop(fuzz_id)
                fuzzer.state.merge_running = False
                #await self._state.db.active_fuzzers.set(fuzzer) # already in db
                await self._state.db.fuzzer_states.set_state(fuzzer)


    async def _stop_fuzzer_internal(self, fuzzer_id: str, stop_on_starter: bool = True):
        active = self._fuzzers.pop(fuzzer_id, None)
        if active is not None:
            
            await self.firstrun_queue.stop_fuzzer(active.id)
            await self.weight_queue.stop_fuzzer(active.id)

            active.state.merge_running = False # TODO: 
            await self._state.db.active_fuzzers.delete(active)
            await self._state.db.fuzzer_states.update_state(active)
            
            if stop_on_starter:
                await self.starter.api_stop_fuzzer(self.pool_id, active.id)


    async def _handle_internal_error(self, fuzzer: ORMFuzzer, agent_mode: AgentMode, agent_status: Optional[Status] = None):
        if agent_mode in [AgentMode.FirstRun, AgentMode.Merge]:
            fuzzer.state.merge_running = False
            if agent_mode == AgentMode.Merge:
                fuzzer.state.fuzz_runs = self._settings.scheduler.merge_interval
            fuzzer.state.merge_internal_errors += 1
            internal_errors = fuzzer.state.merge_internal_errors
        else: #elif agent_mode == AgentMode.Fuzz:
            fuzzer.state.fuzz_internal_errors += 1
            internal_errors = fuzzer.state.fuzz_internal_errors

        await self._state.db.fuzzer_states.update_state(fuzzer)

        if internal_errors > 5:
            await self._stop_fuzzer_internal(fuzzer.id)

            error_code = SchedulerError.InternalError
            if agent_status is not None:
                error_code = SchedulerError.AgentError

            await self.api_gateway.mq_fuzzer_stopped(
                fuzzer.id, fuzzer.rev,
                code=error_code,
                agent_status=agent_status,
            )


    # TODO: separate weight logic
    async def _weight_logic(self, fuzzer: ORMFuzzer, agent_mode: AgentMode, result: AgentOutput):
        if agent_mode != AgentMode.Fuzz:
            return

        old_weight = fuzzer.state.weight

        try:
            stats_base = StatisticsBase(**result.statistics)
            if stats_base.work_time < 5:
                fuzzer.state.weight -= 1
                await self.weight_queue.update_weight(fuzzer.id)
                await self._state.db.fuzzer_states.update_state(fuzzer)

            if result.crashes_found > 0:
                new_cov = 0.0
                if ORMEngineID.is_libfuzzer(fuzzer.engine):
                    stats = StatisticsLibFuzzer(**result.statistics)
                    new_cov = stats.feature_cov
                elif ORMEngineID.is_afl(fuzzer.engine):
                    stats = StatisticsAFL(**result.statistics)
                    new_cov = stats.bitmap_cvg
                
                if new_cov > fuzzer.state.last_crash_coverage:
                    fuzzer.state.weight = self._state.settings.scheduler.default_weight
                else:
                    fuzzer.state.weight -= 1
                fuzzer.state.last_crash_coverage = new_cov

                await self.weight_queue.update_weight(fuzzer.id)
                await self._state.db.fuzzer_states.update_state(fuzzer)

            # update health
            if fuzzer.state.weight <= 0:
                #if old_weight > 0:
                    await self._stop_fuzzer_internal(fuzzer.id)
                    await self.api_gateway.mq_fuzzer_stopped(
                        fuzzer.id, fuzzer.rev,
                        SchedulerError.ZeroWeight,
                    )
            
            elif fuzzer.state.weight <= self._settings.scheduler.warning_weight:
                if old_weight > self._settings.scheduler.warning_weight:
                    await self.api_gateway.mq_fuzzer_stopped(
                        fuzzer.id, fuzzer.rev,
                        SchedulerError.LowWeight,
                    )

            elif fuzzer.state.weight > self._settings.scheduler.warning_weight:
                if old_weight <= self._settings.scheduler.warning_weight:
                    await self.api_gateway.mq_fuzzer_stopped(
                        fuzzer.id, fuzzer.rev,
                        SchedulerError.NormalWeight,
                    )
                    
        except Exception as e:
            self._logger.exception("Unhandled exception in weight logic")


    async def _run_loop(self):
        #async with self._lock:
        while True:
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._run_event.wait(), timeout=5 * 1000)
                self._run_event.clear()
                
            while True:
                try:
                    if self._next_run is None:
                        self._next_run = await self.firstrun_queue.choose_next()
                    if self._next_run is None:
                        self._next_run = await self.weight_queue.choose_next()

                    if self._next_run is None:
                        break
                
                    # skip if stopped
                    if not self._is_actual(
                        id=self._next_run.id,
                        rev=self._next_run.rev,
                        session_id=self._next_run.session_id,
                    ):
                        self._next_run = None
                        continue

                    # try run fuzzer
                    agent_mode = self._select_run_mode(self._next_run)
                    res = await self.starter.api_run_fuzzer(self._next_run, agent_mode)

                    # if pool is busy, then sleep(waiting)
                    if res in {
                        StarterRunFuzzerResult.NoResourcesLeft,
                        StarterRunFuzzerResult.PoolLocked,
                    }:
                        break
                    
                    fuzzer = self._next_run
                    self._next_run = None
                    
                    if res == StarterRunFuzzerResult.PoolTooSmall:
                        await self._stop_fuzzer_internal(
                            fuzzer_id=fuzzer.id,
                            stop_on_starter=True,    
                        )
                        await self.api_gateway.mq_fuzzer_stopped(
                            fuzzer.id, fuzzer.rev,
                            SchedulerError.NotEnoughResources,
                        )

                    elif res == StarterRunFuzzerResult.PoolNotFound:
                        # await self.stop_all_fuzzers() # TODO: 
                        # await self.starter.api_stop_all_fuzzers(self.pool_id)
                        for tmp_fuzzer in self._fuzzers.values():
                            await self._stop_fuzzer_internal(tmp_fuzzer.id, stop_on_starter=False)
                            await self.api_gateway.mq_fuzzer_stopped(
                                tmp_fuzzer.id, tmp_fuzzer.rev,
                                SchedulerError.InternalError,
                            )
                        return

                    else: # elif res == Success:
                    
                        if agent_mode in {AgentMode.FirstRun, AgentMode.Merge}:
                            fuzzer.state.fuzz_runs = 0
                            fuzzer.state.merge_running = True
                        elif agent_mode == AgentMode.Fuzz:
                            fuzzer.state.fuzz_runs += 1
                        else:
                            assert False, f"Unknown agent mode: {agent_mode.value}"

                        await self._state.db.fuzzer_states.update_state(fuzzer)
                except Exception as e:
                    pass


    async def start_fuzzer(self, fuzzer: ORMFuzzer):
        async with self._lock:
            await self._stop_fuzzer_internal(fuzzer.id)

            self._fuzzers[fuzzer.id] = fuzzer
            if not fuzzer.is_verified:
                await self.firstrun_queue.start_fuzzer(fuzzer)
            else:
                await self.weight_queue.start_fuzzer(fuzzer)
            
            await self._state.db.active_fuzzers.set(fuzzer)
        
        self._run_event.set()


    async def stop_fuzzer(self, id: str, rev: str):
        async with self._lock:
            active = self._fuzzers.get(id, None)
            if active is not None:
                await self._stop_fuzzer_internal(active.id)
                if active.rev != rev:
                    # TODO: log
                    pass

    
    async def stop_all_fuzzers(self):
        async with self._lock:
            await self._stop_all_fuzzers()

    async def _stop_all_fuzzers(self):
        await self.starter.api_stop_all_fuzzers(self.pool_id)
        for fuzzer_id in self._fuzzers.keys():
            await self._stop_fuzzer_internal(fuzzer_id, stop_on_starter=False)


    async def update_fuzzer(
        self,
        id: str,
        rev: str,
        cpu_usage: int,
        ram_usage: int,
        tmpfs_size: int,
    ) -> None:
        async with self._lock:
            active = self._fuzzers.get(id, None)

            if active is None:
                await self.api_gateway.mq_fuzzer_stopped(
                    id, rev,
                    SchedulerError.InternalError,
                )
                return

            if active.rev == rev:
                active.cpu_usage = cpu_usage
                active.ram_usage = ram_usage
                active.tmpfs_size = tmpfs_size
                await self._state.db.active_fuzzers.update(active)

            else:
                await self._stop_fuzzer_internal(id)
                await self.api_gateway.mq_fuzzer_stopped(
                    id, rev,
                    SchedulerError.InternalError,
                )
                await self.api_gateway.mq_fuzzer_stopped(
                    active.id, active.rev,
                    SchedulerError.InternalError,
                )


    async def fuzzer_run_result(
        self,
        id: str,
        rev: str,

        session_id: str,
        agent_mode: AgentMode,

        start_time: str,
        finish_time: str,
        result: Optional[AgentOutput],
    ):
        async with self._lock:

            if not self._is_actual(id, rev, session_id): 
                return

            active = self._fuzzers[id]

            if agent_mode in [AgentMode.FirstRun, AgentMode.Merge]:
                active.state.merge_running = False
                await self._state.db.fuzzer_states.update_state(active)
               
            # Agent crashed or send invalid response
            if result is None:
                await self._handle_internal_error(active, agent_mode)
                return

            # Agent/fuzzer exited with error
            elif result.status.code not in {
                agent_errors.E_SUCCESS,
                agent_errors.E_FUZZER_ABORTED, # TODO:
            }:
                # E_INTERNAL_ERROR = 1          - internal

                # E_CONFIG_INVALID = 2          - error
                # E_FUZZER_ABORTED = 3          - normal(displacement/stop) ???
                # E_FUZZER_LAUNCH_ERROR = 4     - error

                # E_RAM_LIMIT_EXCEEDED = 5      - error
                # E_TMPFS_LIMIT_EXCEEDED = 6    - error

                if result.status.code == agent_errors.E_INTERNAL_ERROR:
                    await self._handle_internal_error(active, agent_mode, result.status)

                else:
                    await self._stop_fuzzer_internal(active.id)
                    await self.api_gateway.mq_fuzzer_stopped(
                        active.id, active.rev,
                        agent_status=result.status,
                    )

                return


            ########################################
            # Success run
            ########################################

            # Wrong agent mode for this fuzzer
            if (
                (not active.is_verified and agent_mode != AgentMode.FirstRun) or
                (active.is_verified and agent_mode not in {AgentMode.Fuzz, AgentMode.Merge})
            ):
                self._logger.critical(
                    f"Agent result with mode '{agent_mode.value}' received by '%s' revision(%s)",
                    "normal" if active.is_verified else "first-run",
                    f"id: {id}, rev: {rev}",
                )
                await self._handle_internal_error(active, agent_mode)
                return

            # Handle firstrun success run
            if agent_mode == AgentMode.FirstRun:

                active.state.merge_internal_errors = 0
                await self._state.db.fuzzer_states.update_state(active)

                active.is_verified = True
                await self._state.db.active_fuzzers.update(active)

                await self.firstrun_queue.stop_fuzzer(id)
                await self.weight_queue.start_fuzzer(active)
                await self.api_gateway.mq_fuzzer_verified(active.id, active.rev)

            # Handle fuzz/merge success run
            elif agent_mode in {AgentMode.Fuzz, AgentMode.Merge}:
                if agent_mode == AgentMode.Fuzz:
                    active.state.fuzz_internal_errors = 0
                else:
                    active.state.merge_internal_errors = 0

                await self._state.db.fuzzer_states.update_state(active)

            # TODO: weight logic
            await self._weight_logic(active, agent_mode, result)


    async def pod_finished(
        self,
        id: str,
        rev: str,
        
        session_id: str,
        agent_mode: AgentMode,
        success: bool,
    ):
        self._run_event.set()
        if success:
            return
        
        #else:
        async with self._lock:
            if not self._is_actual(id, rev, session_id):
                return

            await self._handle_internal_error(
                fuzzer=self._fuzzers[id],
                agent_mode=agent_mode,
            )


    def _select_run_mode(self, fuzzer: ORMFuzzer) -> AgentMode:
        if not fuzzer.is_verified:
            return AgentMode.FirstRun
        
        if (
            self._next_run.state.fuzz_runs >= self._settings.scheduler.merge_interval 
            and not self._next_run.state.merge_running
        ):
            return AgentMode.Merge
        else:
            return AgentMode.Fuzz

    
    def _is_actual(self, id: str, rev: str, session_id: str) -> bool:
        active = self._fuzzers.get(id)
        if active is None or active.rev != rev:
            return False
        
        return active.session_id == session_id


