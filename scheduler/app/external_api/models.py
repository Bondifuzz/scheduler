from __future__ import annotations
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from pydantic import Extra

from typing import Optional
from enum import Enum
import logging

from scheduler.app.models import AgentMode, IntEnum, Status

########################################
# Base
########################################

class ErrorModel(BaseModel):
    code: int
    message: str


class ListResultModel(BaseModel):
    pg_num: int
    pg_size: int
    items: list


class ListResponseModel(BaseModel):
    result: ListResultModel


########################################
# Starter
########################################


class StarterRunFuzzerRequestModel(BaseModel):
    user_id: str
    project_id: str
    # pool_id: str # path parameter
    fuzzer_id: str
    fuzzer_rev: str
    fuzzer_engine: str
    fuzzer_lang: str
    image_id: str

    cpu_usage: int = Field(gt=0)
    ram_usage: int = Field(gt=0)
    tmpfs_size: int = Field(gt=0)

    session_id: str
    agent_mode: AgentMode


class StarterRunFuzzerResult(IntEnum):
    Success = 0
    PoolNotFound = 2
    PoolTooSmall = 3
    NoResourcesLeft = 4
    PoolLocked = 5
