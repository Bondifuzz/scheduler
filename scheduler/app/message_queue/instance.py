from __future__ import annotations
from typing import TYPE_CHECKING

from mqtransport import MQApp, SQSApp

# agent
from .agent import MC_FuzzerRunResult

# starter
from .starter import MC_PodFinished

# api-gateway
from .api_gateway import (
    MP_FuzzerStatus,
    MP_FuzzerRunResult,
    MP_FuzzerStopped,
    MP_FuzzerVerified,
)
from .api_gateway import MC_FuzzerStart, MC_FuzzerUpdate, MC_FuzzerStop, MC_PoolStopAllFuzzers

from scheduler.app.message_queue.state import MQAppState

if TYPE_CHECKING:
    from scheduler.app.settings import AppSettings
    from mqtransport import MQApp


class Producers:
    class _api_gateway:
        fuzzer_status: MP_FuzzerStatus
        fuzzer_verified: MP_FuzzerVerified
        fuzzer_run_result: MP_FuzzerRunResult
        fuzzer_stopped: MP_FuzzerStopped

    api_gateway = _api_gateway()


class MQAppInitializer:

    _settings: AppSettings
    _app: MQApp

    @property
    def app(self):
        return self._app

    def __init__(self, settings: AppSettings):
        self._settings = settings
        self._app = None

    async def do_init(self):

        self._app = await self._create_mq_app()
        self._app.state = MQAppState()

        try:
            await self._app.ping()
            await self._configure_channels()

        except:
            await self._app.shutdown()
            raise

    async def _create_mq_app(self):

        mq_broker = self._settings.message_queue.broker.lower()
        mq_settings = self._settings.message_queue

        if mq_broker == "sqs":
            return await SQSApp.create(
                mq_settings.username,
                mq_settings.password,
                mq_settings.region,
                mq_settings.url,
            )

        raise ValueError(f"Unsupported message broker: {mq_broker}")

    async def _create_own_channel(self):
        queues = self._settings.message_queue.queues
        ich = await self._app.create_consuming_channel(queues.scheduler)
        dlq = await self._app.create_producing_channel(queues.dlq)
        ich.use_dead_letter_queue(dlq)
        self._in_channel = ich

    async def _create_other_channels(self):
        queues = self._settings.message_queue.queues
        self._och_api_gateway = await self._app.create_producing_channel(queues.api_gateway)


    def _setup_starter_communication(self, producers: Producers):

        ich = self._in_channel

        # Incoming messages
        ich.add_consumer(MC_PodFinished())


    def _setup_agent_communication(self, producers: Producers):

        ich = self._in_channel

        # Incoming messages
        ich.add_consumer(MC_FuzzerRunResult())


    def _setup_api_gateway_communication(self, producers: Producers):

        ich = self._in_channel
        och = self._och_api_gateway

        # Incoming messages
        ich.add_consumer(MC_FuzzerStart())
        ich.add_consumer(MC_FuzzerUpdate())
        ich.add_consumer(MC_FuzzerStop())
        ich.add_consumer(MC_PoolStopAllFuzzers())

        # Outcoming messages
        producers.api_gateway.fuzzer_verified = MP_FuzzerVerified()
        producers.api_gateway.fuzzer_run_result = MP_FuzzerRunResult()
        producers.api_gateway.fuzzer_status = MP_FuzzerStatus()
        producers.api_gateway.fuzzer_stopped = MP_FuzzerStopped()

        och.add_producer(producers.api_gateway.fuzzer_verified)
        och.add_producer(producers.api_gateway.fuzzer_run_result)
        och.add_producer(producers.api_gateway.fuzzer_status)
        och.add_producer(producers.api_gateway.fuzzer_stopped)

    async def _configure_channels(self):
        await self._create_own_channel()
        await self._create_other_channels()

        state: MQAppState = self.app.state
        state.producers = Producers()

        self._setup_api_gateway_communication(state.producers)
        self._setup_starter_communication(state.producers)
        self._setup_agent_communication(state.producers)


async def mq_init(settings: AppSettings):
    initializer = MQAppInitializer(settings)
    await initializer.do_init()
    return initializer.app

