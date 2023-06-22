from datetime import datetime, timezone
import functools

from .settings import get_app_settings
from pydantic import BaseModel, root_validator, ValidationError
from typing import Dict, Any
from logging import LoggerAdapter


class PrefixedLogger(LoggerAdapter):
    def process(self, msg, kwargs):
        return f"{self.extra['prefix']} {msg}", kwargs


def rfc3339_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def check_empty_strings(data: Dict[str, Any]):

    names = []
    for name, value in data.items():
        if isinstance(value, str):
            if len(value) == 0:
                names.append(name)

    return names


def check_at_least_one_field_set(data: Dict[str, Any]):
    return len(list(filter(lambda x: x is not None, data.values()))) > 0


class PydanticBaseModel(BaseModel):
    @root_validator
    def check_empty_strings(cls, data: Dict[str, Any]):

        names = check_empty_strings(data)
        if not names:
            return data

        raise ValidationError(
            [
                {
                    "loc": names,
                    "msg": "Empty strings not allowed",
                    "type": "value_error.string_empty",
                }
            ],
        )


class PydanticPartialBaseModel(PydanticBaseModel):
    @root_validator
    def check_at_least_one_field_set(cls, data: Dict[str, Any]):

        if check_at_least_one_field_set(data):
            return data

        raise ValidationError(
            [
                {
                    "loc": list(data.keys()),
                    "msg": "At least one field must be set",
                    "type": "value_error.at_least_one_set",
                }
            ],
        )


def get_unixtime() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def testing_only(func):

    """Provides decorator, which forbids
    calling dangerous functions in production"""

    settings = get_app_settings()
    is_danger = settings.environment.name == "prod"

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):

        if is_danger:
            err = f"Function '{func.__name__}' is allowed to call only in testing mode"
            help = "Please, check 'ENVIRONMENT' variable is not set to 'prod'"
            raise RuntimeError(f"{err}. {help}")

        return await func(*args, **kwargs)

    return wrapper
