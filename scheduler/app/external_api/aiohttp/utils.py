from __future__ import annotations
import functools

from aiohttp import ClientError
from pydantic import BaseModel

from ..errors import EAPIClientError


def _default(obj):
    if isinstance(obj, BaseModel):
        return obj.dict()
    raise TypeError

try:
    # fmt: off
    import orjson  # type: ignore
    json_dumps = lambda x: orjson.dumps(x, _default).decode()
    json_loads = lambda x: orjson.loads(x)
    # fmt: on

except ModuleNotFoundError:
    import json  # fmt: skip
    json_dumps = lambda x: json.dumps(x, default=_default)
    json_loads = lambda x: json.loads(x)

def wrap_aiohttp_errors(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
        except ClientError as e:
            raise EAPIClientError(e) from e
        return result

    return wrapper