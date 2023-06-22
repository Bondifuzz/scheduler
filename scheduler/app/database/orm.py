from __future__ import annotations
from typing import TYPE_CHECKING
from scheduler.app.models import FuzzerHealth

from scheduler.app.settings import AppSettings

from ..utils import PydanticBaseModel
from typing import Optional
from enum import Enum
from pydantic.fields import Field

import logging


class ORMBase(PydanticBaseModel):
    def __init__(self, **data):
        if not __debug__:
            name = self.__class__.__name__
            logging.warning(f"{name}: Using constructor instead of from_XXX() method")
        super().__init__(**data)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data) if __debug__ else cls.construct(**data)

    @classmethod
    def from_kwargs(cls, **data):
        return cls(**data) if __debug__ else cls.construct(**data)


class ORMFuzzerState(ORMBase):
    weight: int                  = Field()
    last_crash_coverage: float   = Field(default=0.0, ge=0)
    current_health: FuzzerHealth = Field(default=FuzzerHealth.Ok)

    fuzz_runs: int               = Field(ge=0)
    merge_running: bool

    fuzz_internal_errors: int
    merge_internal_errors: int


    @staticmethod
    def default(settings: AppSettings) -> ORMFuzzerState:
        return ORMFuzzerState(
            weight=settings.scheduler.default_weight,

            merge_running=False,
            fuzz_runs=0,

            fuzz_internal_errors=0,
            merge_internal_errors=0,
        )

    # TODO:
    def restart(self):
        self.fuzz_runs = 0
        self.merge_running = False
        self.fuzz_internal_errors = 0
        self.merge_internal_errors = 0


class ORMEngineID(str, Enum):
    # afl binding
    afl = "afl"
    afl_rs = "afl.rs"
    sharpfuzz_afl = "sharpfuzz-afl"

    # libfuzzer binding
    libfuzzer = "libfuzzer"
    jazzer = "jazzer"
    atheris = "atheris"
    cargo_fuzz = "cargo-fuzz"
    go_fuzz_libfuzzer = "go-fuzz-libfuzzer"
    sharpfuzz_libfuzzer = "sharpfuzz-libfuzzer"

    @staticmethod
    def is_afl(engine_id: ORMEngineID):
        return engine_id in {
            ORMEngineID.afl,
            ORMEngineID.afl_rs,
            ORMEngineID.sharpfuzz_afl,
        }

    @staticmethod
    def is_libfuzzer(engine_id: ORMEngineID):
        return engine_id in {
            ORMEngineID.libfuzzer,
            ORMEngineID.jazzer,
            ORMEngineID.atheris,
            ORMEngineID.cargo_fuzz,
            ORMEngineID.go_fuzz_libfuzzer,
            ORMEngineID.sharpfuzz_libfuzzer,
        }


class ORMFuzzer(ORMBase):
    user_id: str
    project_id: str
    pool_id: str

    id: str
    rev: str
    engine: ORMEngineID
    lang: str
    image_id: str

    cpu_usage: int = Field(gt=0)
    ram_usage: int = Field(gt=0)
    tmpfs_size: int = Field(gt=0)

    session_id: str
    is_verified: bool  # first-run complete or not

    state: Optional[ORMFuzzerState]
