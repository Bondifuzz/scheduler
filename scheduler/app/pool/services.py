from typing import Optional
from mqtransport import MQApp
from scheduler.app.database.orm import ORMFuzzer

from scheduler.app.external_api.aiohttp.external_api import ExternalAPI
from scheduler.app.message_queue.state import MQAppState
from scheduler.app.models import SCHEDULER_ERROR_STR, FuzzerHealth, AgentMode, SchedulerError, Status


class Starter:

    #mq_app: MQApp
    mq_state: MQAppState
    external_api: ExternalAPI

    def __init__(self, mq_state: MQAppState, external_api: ExternalAPI) -> None:
        #self.mq_app = mq_app
        self.mq_state = mq_state
        self.external_api = external_api

    async def api_stop_fuzzer(self, pool_id: str, fuzzer_id: str):
        await self.external_api.starter.stop_fuzzer(pool_id, fuzzer_id)

    async def api_stop_all_fuzzers(self, pool_id: str):
        await self.external_api.starter.stop_all_fuzzers(pool_id)

    async def api_run_fuzzer(self, fuzzer: ORMFuzzer, agent_mode: AgentMode):
        return await self.external_api.starter.run_fuzzer(fuzzer, agent_mode)


class ApiGateway:

    #mq_app: MQApp
    mq_state: MQAppState
    external_api: ExternalAPI

    def __init__(self, mq_state: MQAppState, external_api: ExternalAPI) -> None:
        #self.mq_app = mq_app
        self.mq_state = mq_state
        self.external_api = external_api

    async def mq_fuzzer_stopped(
        self,
        id: str,
        rev: str,
        code: Optional[SchedulerError] = None,
        agent_status: Optional[Status] = None,
    ):
        if code is None and agent_status:
            code = SchedulerError.AgentError

        assert code, "code or agent_status must be provided!"

        health = FuzzerHealth.Error
        if code in {SchedulerError.ZeroWeight}:
            health = FuzzerHealth.Warning

        await self.mq_state.producers.api_gateway.fuzzer_stopped.produce(
            fuzzer_id=id,
            fuzzer_rev=rev,
            fuzzer_health=health,
            fuzzer_status=Status(
                code=code,
                message=SCHEDULER_ERROR_STR[code],
            ),
            agent_status=agent_status,
        )

    async def mq_fuzzer_verified(
        self,
        id: str,
        rev: str,
    ):
        await self.mq_state.producers.api_gateway.fuzzer_verified.produce(
            fuzzer_id=id,
            fuzzer_rev=rev,
        )