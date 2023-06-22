from __future__ import annotations
from typing import TYPE_CHECKING

import logging

if TYPE_CHECKING:
    from ..settings import AppSettings
    from .abstract import IExternalAPI


async def external_api_init(settings: AppSettings) -> IExternalAPI:

    logger = logging.getLogger("api.external")
    api_client = settings.api.client_module
    # db_engine = settings.external_api.endpoints

    if api_client == "aiohttp":
        logger.info("Using aiohttp client")
        from .aiohttp.external_api import ExternalAPI
        api = await ExternalAPI.create(settings)
    # elif api_client == "grpc":
    #     logger.info("Using grpc client")
    #     from .grpc.external_api import ExternalAPI
    #     api = await ExternalAPI.create(settings)
    else:
        raise ValueError(f"Invalid external api engine '{api_client}'")

    return api
