from __future__ import annotations
from typing import TYPE_CHECKING

from scheduler.app.models import AgentMode
from mqtransport.participants import Consumer, Producer
from mqtransport.errors import ConsumeMessageError
from pydantic import BaseModel

if TYPE_CHECKING:
    from mqtransport import MQApp
    from scheduler.app.message_queue.state import MQAppState


class MC_PodFinished(Consumer):
    name: str = "starter.pods.finished"

    class Model(BaseModel):
        user_id: str
        project_id: str
        pool_id: str
        fuzzer_id: str
        fuzzer_rev: str
        fuzzer_lang: str
        fuzzer_engine: str

        session_id: str
        agent_mode: AgentMode
        success: bool

    async def consume(self, msg: Model, app: MQApp):
        state: MQAppState = app.state
        await state.pool_manager.pod_finished(
            pool_id=msg.pool_id,
            id=msg.fuzzer_id,
            rev=msg.fuzzer_rev,
            session_id=msg.session_id,
            agent_mode=msg.agent_mode,
            success=msg.success,
        )


