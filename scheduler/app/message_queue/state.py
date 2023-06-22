from __future__ import annotations
from typing import TYPE_CHECKING

import random

if TYPE_CHECKING:
    from scheduler.app.settings import AppSettings
    from scheduler.app.database.abstract import IDatabase
    from scheduler.app.message_queue.instance import Producers
    from scheduler.app.external_api.abstract import IExternalAPI
    from scheduler.app.pool.pool_manager import PoolManager


class MQAppState:
    producers: Producers
    db: IDatabase
    settings: AppSettings
    external_api: IExternalAPI

    pool_manager: PoolManager

    session_id: str

    def __init__(self):
        self.session_id = str(random.randint(0, 0xFFFFFFFF))
