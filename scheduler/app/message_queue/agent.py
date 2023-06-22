from __future__ import annotations
from typing import TYPE_CHECKING
from scheduler.app.database.orm import ORMEngineID

from scheduler.app.models import (
    AgentOutput,
    AgentMode,
    Status,
)
from mqtransport.participants import Consumer, Producer
from mqtransport.errors import ConsumeMessageError
from typing import Optional
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from mqtransport import MQApp
    from scheduler.app.message_queue.state import MQAppState


class MC_FuzzerRunResult(Consumer):
    name: str = "agent.fuzzer.result"

    class Model(BaseModel):
        user_id: str
        project_id: str
        pool_id: str
        fuzzer_id: str
        fuzzer_rev: str
        fuzzer_engine: ORMEngineID
        fuzzer_lang: str

        session_id: str
        agent_mode: AgentMode

        start_time: str
        finish_time: str
        agent_result: Optional[AgentOutput]

    async def consume(self, msg: Model, app: MQApp):
        state: MQAppState = app.state

        if msg.agent_result is not None:
            if msg.agent_result.statistics is not None or msg.agent_result.crashes_found > 0:
                await state.producers.api_gateway.fuzzer_run_result.produce(
                    user_id=msg.user_id,
                    project_id=msg.project_id,
                    pool_id=msg.pool_id,
                    fuzzer_id=msg.fuzzer_id,
                    fuzzer_rev=msg.fuzzer_rev,
                    fuzzer_engine=msg.fuzzer_engine,
                    fuzzer_lang=msg.fuzzer_lang,

                    start_time=msg.start_time,
                    finish_time=msg.finish_time,
                    statistics=msg.agent_result.statistics,
                    crashes_found=msg.agent_result.crashes_found,
                )

        await state.pool_manager.fuzzer_run_result(
            pool_id=msg.pool_id,
            id=msg.fuzzer_id,
            rev=msg.fuzzer_rev,

            session_id=msg.session_id,
            agent_mode=msg.agent_mode,

            start_time=msg.start_time,
            finish_time=msg.finish_time,
            result=msg.agent_result,
        )

