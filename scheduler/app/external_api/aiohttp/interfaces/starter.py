from __future__ import annotations
from typing import TYPE_CHECKING
from scheduler.app.external_api.errors import EAPIServerError
from scheduler.app.models import AgentMode

from scheduler.app.utils import PrefixedLogger
from scheduler.app.external_api.models import (
    StarterRunFuzzerRequestModel,
    StarterRunFuzzerResult,
)
from scheduler.app.external_api.abstract import IStarterAPI
from ..utils import wrap_aiohttp_errors
from .base import AIOHttpAPI

if TYPE_CHECKING:
    from scheduler.app.settings import AppSettings
    from scheduler.app.database.orm import ORMFuzzer

class StarterAPI(AIOHttpAPI, IStarterAPI):

    """ Communication with Starter """

    def __init__(self, settings: AppSettings):
        super().__init__(settings.api.endpoints.starter)
        extra = {"prefix": f"[{self.__class__.__name__}]"}
        self._logger = PrefixedLogger(self._logger, extra)
        self._base_path = "/api/v1"

    @wrap_aiohttp_errors
    async def run_fuzzer(self, fuzzer: ORMFuzzer, agent_mode: AgentMode) -> StarterRunFuzzerResult:
        json_data = StarterRunFuzzerRequestModel(
            user_id=fuzzer.user_id,
            project_id=fuzzer.project_id,
            #pool_id=fuzzer.pool_id, # path parameter
            fuzzer_id=fuzzer.id,
            fuzzer_rev=fuzzer.rev,
            fuzzer_engine=fuzzer.engine,
            fuzzer_lang=fuzzer.lang,
            image_id=fuzzer.image_id,

            cpu_usage=fuzzer.cpu_usage,
            ram_usage=fuzzer.ram_usage,
            tmpfs_size=fuzzer.tmpfs_size,

            session_id=fuzzer.session_id,
            agent_mode=agent_mode,
        )
        url = f"{self._base_path}/pools/{fuzzer.pool_id}/fuzzers"
        response = await self._session.post(url, json=json_data)
        try:
            await self.parse_response_no_model(response)
            return StarterRunFuzzerResult.Success # TODO:
            
        except EAPIServerError as e:
            return StarterRunFuzzerResult(e.code) # TODO:


    @wrap_aiohttp_errors
    async def stop_fuzzer(self, pool_id: str, fuzzer_id: str):
        url = f"{self._base_path}/pools/{pool_id}/fuzzers/{fuzzer_id}"
        response = await self._session.delete(url)
        await self.parse_response_no_model(response)

    @wrap_aiohttp_errors
    async def stop_all_fuzzers(self, pool_id: str):
        url = f"{self._base_path}/pools/{pool_id}/fuzzers"
        response = await self._session.delete(url)
        await self.parse_response_no_model(response)
