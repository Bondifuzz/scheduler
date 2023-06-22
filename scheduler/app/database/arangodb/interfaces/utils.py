from scheduler.app.settings import CollectionSettings
from scheduler.app.database.errors import DatabaseError

from aiohttp.client_exceptions import ClientConnectionError
from aioarangodb.errno import UNIQUE_CONSTRAINT_VIOLATED, DOCUMENT_NOT_FOUND
from aioarangodb.exceptions import (
    ArangoError,
    CursorEmptyError,
    DocumentDeleteError,
    DocumentInsertError,
    DocumentReplaceError,
)

from typing import Type
import functools


def maybe_unknown_error(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            res = await func(*args, **kwargs)
        except (ArangoError, ClientConnectionError) as e:
            raise DatabaseError(e) from e

        return res

    return wrapper


def maybe_not_found(ExceptionRaised: Type[DatabaseError]):
    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            try:
                res = await func(*args, **kwargs)
            except CursorEmptyError as e:
                raise ExceptionRaised() from e
            except DocumentDeleteError as e:
                if e.error_code == DOCUMENT_NOT_FOUND:
                    raise ExceptionRaised() from e
                raise

            return res

        return wrapped

    return wrapper


def maybe_not_found_none(ExceptionRaised: Type[DatabaseError]):
    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            res = await func(*args, **kwargs)
            if not res:
                raise ExceptionRaised()

            return res

        return wrapped

    return wrapper


def maybe_already_exists(ExceptionRaised: Type[DatabaseError]):
    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            try:
                res = await func(*args, **kwargs)
            except (DocumentInsertError, DocumentReplaceError) as e:
                if e.error_code == UNIQUE_CONSTRAINT_VIOLATED:
                    raise ExceptionRaised() from e
                raise
            return res

        return wrapped

    return wrapper
