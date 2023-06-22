from __future__ import annotations
import random
from typing import TYPE_CHECKING

from scheduler.app.models import (
    SCHEDULER_ERROR_STR,
    AgentOutput,
    FuzzerHealth,
    SchedulerError,
    Status,
)

from typing import Optional
from pydantic import BaseModel, Field, validator

from scheduler.app.database.orm import ORMFuzzer, ORMEngineID, ORMFuzzerState
from mqtransport.participants import Consumer, Producer
from mqtransport.errors import ConsumeMessageError

if TYPE_CHECKING:
    from mqtransport import MQApp
    from scheduler.app.message_queue.state import MQAppState
    from scheduler.app.settings import AppSettings
    

class MC_FuzzerStart(Consumer):
    name: str = "api-gateway.fuzzer.start"

    class Model(BaseModel):
        user_id: str
        project_id: str
        pool_id: str
        fuzzer_id: str
        fuzzer_rev: str
        fuzzer_engine: ORMEngineID
        fuzzer_lang: str
        image_id: str

        cpu_usage: int = Field(gt=0)
        ram_usage: int = Field(gt=0)
        tmpfs_size: int = Field(gt=0)

        is_verified: bool  # first-run complete or not
        reset_state: bool

    async def consume(self, msg: Model, app: MQApp):
        state: MQAppState = app.state
        try:
            fuzzer = ORMFuzzer(
                session_id=str(random.randint(0, 0xFFFFFFFF)),
                is_verified=msg.is_verified,

                user_id=msg.user_id,
                project_id=msg.project_id,
                pool_id=msg.pool_id,
                id=msg.fuzzer_id,
                rev=msg.fuzzer_rev,
                engine=msg.fuzzer_engine,
                lang=msg.fuzzer_lang,
                image_id=msg.image_id,

                cpu_usage=msg.cpu_usage,
                ram_usage=msg.ram_usage,
                tmpfs_size=msg.tmpfs_size,
            )
            fuzzer.state = await state.db.fuzzer_states.get_state(fuzzer)
            if fuzzer.state is None or msg.reset_state:
                fuzzer.state = ORMFuzzerState.default(state.settings)
                await state.db.fuzzer_states.set_state(fuzzer)

            await state.pool_manager.start_fuzzer(msg.pool_id, fuzzer)
        except:
            self.logger.exception(
                "Failed to start fuzzer(id: %s, rev: %s)!",
                msg.fuzzer_id, msg.fuzzer_rev
            )
            await state.producers.api_gateway.fuzzer_stopped.produce_args(
                msg.fuzzer_id, msg.fuzzer_rev,
                SchedulerError.InternalError
            )
            raise ConsumeMessageError() # TODO: DAITE REST/GRPC ((((


class MC_FuzzerUpdate(Consumer):
    name: str = "api-gateway.fuzzer.update"

    class Model(BaseModel):
        pool_id: str
        fuzzer_id: str
        fuzzer_rev: str

        cpu_usage: int = Field(gt=0)
        ram_usage: int = Field(gt=0)
        tmpfs_size: int = Field(gt=0)

    async def consume(self, msg: Model, app: MQApp):
        state: MQAppState = app.state

        try:
            await state.pool_manager.update_fuzzer(
                pool_id=msg.pool_id,
                id=msg.fuzzer_id,
                rev=msg.fuzzer_rev,
                cpu_usage=msg.cpu_usage,
                ram_usage=msg.ram_usage,
                tmpfs_size=msg.tmpfs_size,
            )
        except:
            self.logger.exception(
                "Failed to update fuzzer resources(id: %s, rev: %s)!",
                msg.fuzzer_id, msg.fuzzer_rev
            )
            await state.producers.api_gateway.fuzzer_stopped.produce_args(
                msg.fuzzer_id, msg.fuzzer_rev,
                SchedulerError.InternalError
            )
            raise ConsumeMessageError()


class MC_FuzzerStop(Consumer):
    name: str = "api-gateway.fuzzer.stop"

    class Model(BaseModel):
        pool_id: str
        fuzzer_id: str
        fuzzer_rev: str

    async def consume(self, msg: Model, app: MQApp):
        state: MQAppState = app.state

        try:
            await state.pool_manager.stop_fuzzer(
                pool_id=msg.pool_id,
                id=msg.fuzzer_id,
                rev=msg.fuzzer_rev,
            )
        except:
            self.logger.exception(
                "Failed to stop fuzzer(id: %s, rev: %s)!",
                msg.fuzzer_id, msg.fuzzer_rev
            )
            await state.producers.api_gateway.fuzzer_stopped.produce_args(
                msg.fuzzer_id, msg.fuzzer_rev,
                SchedulerError.InternalError
            )
            raise ConsumeMessageError() # TODO: DAITE REST/GRPC ((((


class MC_PoolStopAllFuzzers(Consumer):
    name: str = "api-gateway.pool.stop_all_fuzzers"

    class Model(BaseModel):
        pool_id: str

    async def consume(self, msg: Model, app: MQApp):
        state: MQAppState = app.state

        try:
            await state.pool_manager.stop_all_fuzzers(
                pool_id=msg.pool_id,
            )
        except:
            self.logger.exception(
                "Failed to stop fuzzers in pool %s!",
                msg.pool_id,
            )
            raise ConsumeMessageError() # TODO: DAITE REST/GRPC ((((
    



##############


class MP_FuzzerVerified(Producer):
    name: str = "scheduler.fuzzer.verified"

    class Model(BaseModel):
        fuzzer_id: str
        fuzzer_rev: str


# error/zero weight/...
class MP_FuzzerStopped(Producer):
    name: str = "scheduler.fuzzer.stopped"

    class Model(BaseModel):
        fuzzer_id: str
        fuzzer_rev: str

        fuzzer_health: FuzzerHealth # warn, err
        fuzzer_status: Status
        agent_status: Optional[Status]


    async def produce_args(
        self,
        id: str,
        rev: str,
        fuzzer_code: Optional[SchedulerError] = None,
        agent_status: Optional[Status] = None
    ):
        if fuzzer_code is None and agent_status:
            fuzzer_code = SchedulerError.AgentError

        assert fuzzer_code, "fuzzer_code or agent_status must be provided!"

        health = FuzzerHealth.Error
        if fuzzer_code in {SchedulerError.ZeroWeight}:
            health = FuzzerHealth.Warning

        await self.produce(
            fuzzer_id=id,
            fuzzer_rev=rev,
            fuzzer_health=health,
            fuzzer_status=Status(
                code=fuzzer_code,
                message=SCHEDULER_ERROR_STR[fuzzer_code],
            ),
            agent_status=agent_status,
        )


class MP_FuzzerStatus(Producer):
    name: str = "scheduler.fuzzer.status"

    class Model(BaseModel):
        fuzzer_id: str
        fuzzer_rev: str

        fuzzer_health: FuzzerHealth # ok, warn
        fuzzer_status: Status


    async def produce_args(
        self,
        id: str,
        rev: str,
        status_code: SchedulerError,
        health: Optional[FuzzerHealth] = None
    ):
        if health is None:
            if status_code in [SchedulerError.Success, SchedulerError.NormalWeight]:
                health = FuzzerHealth.Ok
            elif status_code in [SchedulerError.LowWeight]:
                health = FuzzerHealth.Warning
            else:
                health = FuzzerHealth.Error

        await self.produce(
            fuzzer_id=id,
            fuzzer_rev=rev,
            fuzzer_health=health,
            fuzzer_status=Status(
                code=status_code,
                message=SCHEDULER_ERROR_STR[status_code],
            )
        )


class MP_FuzzerRunResult(Producer):
    name: str = "scheduler.fuzzer.result"

    class Model(BaseModel):
        user_id: str
        project_id: str
        pool_id: str
        fuzzer_id: str
        fuzzer_rev: str
        fuzzer_engine: str
        fuzzer_lang: str

        start_time: str
        finish_time: str

        statistics: Optional[dict]
        crashes_found: int

        @validator("start_time", "finish_time", pre=True)
        def validate_time(cls, value: str):
            if not value.endswith("Z"):
                raise ValueError("Not a valid rfc3339 time")
            return value


    async def produce_args(
        self,
        fuzzer: ORMFuzzer,
        result: AgentOutput
    ):
        await self.produce(
            user_id=fuzzer.user_id,
            project_id=fuzzer.project_id,
            pool_id=fuzzer.pool_id,
            fuzzer_id=fuzzer.id,
            fuzzer_rev=fuzzer.rev,
            fuzzer_engine=fuzzer.engine,
            fuzzer_lang=fuzzer.lang,
            statistics=result.statistics,
            crashes_found=result.crashes_found,
        )

