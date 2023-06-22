from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, root_validator, validator


class StrEnum(str, Enum):
    """Enum where members are also (and must be) strs"""


class IntEnum(int, Enum):
    """Enum where members are also (and must be) ints"""


class AgentMode(StrEnum):
    FirstRun = "firstrun"
    Fuzz = "fuzzing"
    Merge = "merge"


# TODO: rename "error" to smth else?
class SchedulerError(StrEnum):
    Success = "E_SUCCESS"
    InternalError = "E_INTERNAL_ERROR"
    AgentError = "E_AGENT_ERROR"
    NotEnoughResources = "E_NOT_ENOUGH_RESOURCES"
    NormalWeight = "E_NORMAL_WEIGHT"
    LowWeight = "E_LOW_WEIGHT"
    ZeroWeight = "E_ZERO_WEIGHT"


SCHEDULER_ERROR_STR = {
    SchedulerError.Success: "Success",
    SchedulerError.InternalError: "Internal error occurred. Please, contact administrator.",
    SchedulerError.AgentError: "Agent error",
    SchedulerError.NormalWeight: "Fuzzer performance is ok",
    SchedulerError.LowWeight: "Warning: Fuzzer performance is low!",
    SchedulerError.ZeroWeight: "Fuzzer stopped due to very low performance!",
    SchedulerError.NotEnoughResources: "Not enough resources in cluster to run fuzzer!",
}


class Status(BaseModel):

    code: str
    """ Agent exit code """

    message: Optional[str]
    """ Agent exit status in human-readable format """

    details: Optional[str]
    """ Error details. Usually, it's long and verbose message """


class Metrics(BaseModel):

    tmpfs: int
    """ Amount of tmpfs space consumed during fuzzing session """

    memory: int
    """ Amount of ram consumed during fuzzing session """


class FuzzerHealth(StrEnum):
    Warning = "Warning"
    Error = "Error"
    Ok = "Ok"


class AgentOutput(BaseModel):
    status: Status
    metrics: Metrics
    crashes_found: int
    statistics: Optional[dict]


class StatisticsBase(BaseModel):

    work_time: int
    """ Fuzzer work time """


class StatisticsLibFuzzer(StatisticsBase):

    """Get LibFuzzer statistics from scheduler"""

    execs_per_sec: int
    """ Average count of executions per second """

    edge_cov: int
    """ Edge coverage """

    feature_cov: int
    """ Feature coverage """

    peak_rss: int
    """ Max RAM usage in bytes """

    execs_done: int
    """ Count of fuzzing iterations executed """

    corpus_entries: int
    """ Count of files in merged corpus """

    corpus_size: int
    """ The size of generated corpus in bytes """


class StatisticsAFL(StatisticsBase):

    """Get AFL statistics from scheduler"""

    cycles_done: int
    """queue cycles completed so far"""

    cycles_wo_finds: int
    """number of cycles without any new paths found"""

    execs_done: int
    """number of execve() calls attempted"""

    execs_per_sec: float
    """overall number of execs per second"""

    corpus_count: int
    """total number of entries in the queue"""

    corpus_favored: int
    """number of queue entries that are favored"""

    corpus_found: int
    """number of entries discovered through local fuzzing"""

    corpus_variable: int
    """number of test cases showing variable behavior"""

    stability: float
    """percentage of bitmap bytes that behave consistently"""

    bitmap_cvg: float
    """percentage of edge coverage found in the map so far"""

    slowest_exec_ms: int
    """real time of the slowest execution in ms"""

    peak_rss_mb: int
    """max rss usage reached during fuzzing in MB"""

