from __future__ import annotations
from typing import Any, Callable, Optional, Type
from logging import Logger, getLogger

from aiohttp import ClientError, ClientResponse, ClientSession
from pydantic import ValidationError, BaseModel
from scheduler.app.external_api.abstract import APIBase

from ..utils import json_dumps, json_loads

from ...models import ErrorModel, ListResponseModel
from ...errors import (
    EAPIClientError,
    EAPIResponseParseError,
    EAPIServerError,
    ExternalAPIError,
)


class AIOHttpAPI(APIBase):

    """Base class for all external APIs"""

    _session: ClientSession
    _logger: Logger

    def __init__(self, endpoint_url: str):
        self._logger = getLogger("api.external")
        self._session = ClientSession(
            json_serialize=json_dumps,
            base_url=endpoint_url,
        )

    async def close(self):
        await self._session.close()

    async def log_api_error(
        self,
        response: ClientResponse,
        details: str,
    ):
        msg = "API call failed. Status code: %d. Response body:\n%s"
        self._logger.debug(msg, response.status, await response.text())
        self._logger.debug("Error details: %s", details)

    @staticmethod
    def _default_status_allowed(response: ClientResponse):
        return response.status in [200, 201, 202, 204]

    @staticmethod
    def _parse_list_response(json_data: Any):

        try:
            parsed = ListResponseModel.parse_obj(json_data)
        except ValidationError as e:
            raise EAPIResponseParseError() from e

        return parsed.result

    @staticmethod
    def _parse_error_and_raise(json_data: Any):

        if not isinstance(json_data, dict):
            raise EAPIResponseParseError()

        try:
            error = ErrorModel.parse_obj(json_data["error"])
        except (KeyError, ValidationError) as e:
            raise EAPIResponseParseError() from e

        raise EAPIServerError(error.code, error.message)

    @staticmethod
    def _parse_obj(
        json_data: Any,
        response_model: Type[BaseModel],
        grab_result: bool = False,
    ):
        if not isinstance(json_data, dict):
            raise EAPIResponseParseError()

        try:
            if grab_result:
                data = response_model.parse_obj(json_data["result"])
            else:
                data = response_model.parse_obj(json_data)

        except (KeyError, ValidationError) as e:
            raise EAPIResponseParseError() from e

        return data

    @staticmethod
    async def _parse_json(response: ClientResponse):

        try:
            result = await response.json(loads=json_loads)
        except ValueError as e:
            raise EAPIResponseParseError() from e

        return result

    async def parse_response(
        self,
        response: ClientResponse,
        response_model: Type[BaseModel],
        status_allowed_fn: Optional[Callable] = None,
        grab_result: bool = True,
    ):
        if status_allowed_fn is None:
            status_allowed_fn = self._default_status_allowed

        try:
            json_data = await self._parse_json(response)
            if not status_allowed_fn(response):
                self._parse_error_and_raise(json_data)

            result = self._parse_obj(
                json_data,
                response_model,
                grab_result,
            )

        except ExternalAPIError as e:
            await self.log_api_error(response, str(e))
            raise

        return result

    def parse_response_no_model(
        self,
        response: ClientResponse,
        status_allowed_fn: Optional[Callable] = None,
    ):
        return self.parse_response(
            response,
            BaseModel,
            status_allowed_fn,
            False,
        )

    async def paginate(
        self,
        url: str,
        response_model: Type[BaseModel],
        status_allowed_fn: Optional[Callable] = None,
        **kwargs,
    ):
        if status_allowed_fn is None:
            status_allowed_fn = self._default_status_allowed

        if "params" not in kwargs:
            kwargs["params"] = dict()

        try:
            pg_num = 0
            while True:

                # Fetch next page
                kwargs["params"].update({"pg_num": pg_num})
                async with self._session.get(url, **kwargs) as response:

                    # Ensure no errors occurred
                    json_data = await self._parse_json(response)
                    if not status_allowed_fn(response):
                        self._parse_error_and_raise(json_data)

                    # Parse response
                    result = self._parse_list_response(json_data)
                    pg_size = result.pg_size
                    items = result.items

                    # No items in page -> exit
                    if not items:
                        break

                    # Yield parsed item
                    for item in items:
                        yield self._parse_obj(item, response_model)

                    # Page not full -> next page will be empty
                    if len(items) < pg_size:
                        break

                    pg_num += 1

        except ClientError as e:
            raise EAPIClientError(e) from e

        except ExternalAPIError as e:
            await self.log_api_error(response, str(e))
            raise
