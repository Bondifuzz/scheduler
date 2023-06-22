from __future__ import annotations
from typing import TYPE_CHECKING

import logging
from .interfaces.starter import StarterAPI
from ..abstract import IExternalAPI

if TYPE_CHECKING:
    from ...settings import AppSettings
    from ..abstract import IStarterAPI
    from aiohttp import ClientSession


class ExternalAPI(IExternalAPI):

    _logger: logging.Logger
    _starter: IStarterAPI
    _session: ClientSession
    _is_closed: bool

    @property
    def starter(self):
        return self._starter

    async def _init(self, settings: AppSettings):
        self._is_closed = True
        self._starter = StarterAPI(settings)
        self._is_closed = False

    @staticmethod
    async def create(settings):
        _self = ExternalAPI()
        await _self._init(settings)
        return _self

    async def close(self):

        assert not self._is_closed, "External API sessions have been already closed"

        sessions = [
            self._starter,
        ]

        for session in sessions:
            await session.close()

        self._is_closed = True

    def __del__(self):
        if not self._is_closed:
            self._logger.error("External API sessions have not been closed")
