from pydantic import BaseModel, root_validator
from pydantic import Field, AnyHttpUrl, AnyUrl
from pydantic import BaseSettings as _BaseSettings
from typing import Dict, Any, Optional
from contextlib import suppress
from functools import lru_cache

# fmt: off
with suppress(ModuleNotFoundError):
    import dotenv; dotenv.load_dotenv()
# fmt: on


class BaseSettings(_BaseSettings):
    @root_validator
    def check_empty_strings(cls, data: Dict[str, Any]):
        for name, value in data.items():
            if isinstance(value, str):
                if len(value) == 0:
                    var = f"{cls.__name__}.{name}"
                    raise ValueError(f"Variable '{var}': empty string not allowed")

        return data


class EnvironmentSettings(BaseSettings):
    name: str = Field(env="ENVIRONMENT", regex=r"^(dev|prod|test)$")
    shutdown_timeout: int = Field(env="SHUTDOWN_TIMEOUT")
    service_name: Optional[str] = Field(env="SERVICE_NAME")
    service_version: Optional[str] = Field(env="SERVICE_VERSION")
    commit_id: Optional[str] = Field(env="COMMIT_ID")
    build_date: Optional[str] = Field(env="BUILD_DATE")
    commit_date: Optional[str] = Field(env="COMMIT_DATE")
    git_branch: Optional[str] = Field(env="GIT_BRANCH")

    @root_validator(skip_on_failure=True)
    def check_values_for_production(cls, data: Dict[str, Any]):
        if data["name"] != "prod":
            return data

        vars = []
        for name, value in data.items():
            if value is None:
                vars.append(name.upper())

        if vars:
            raise ValueError(f"Variables must be set in production mode: {vars}")

        return data


class DatabaseSettings(BaseSettings):
    engine: str = Field(regex=r"^arangodb$")
    url: AnyHttpUrl
    username: str
    password: str
    name: str

    class Config:
        env_prefix = "DB_"


class CollectionSettings(BaseSettings):
    active_fuzzers: str = "ActiveFuzzers"
    fuzzer_states: str = "FuzzerStates"
    unsent_messages: str = "UnsentMessages"


class MessageQueues(BaseSettings):
    api_gateway: str
    scheduler: str
    dlq: str

    class Config:
        env_prefix = "MQ_QUEUE_"


class MessageQueueSettings(BaseSettings):
    queues: MessageQueues
    broker: str = Field(regex="^sqs$")
    url: AnyUrl
    region: str
    username: str
    password: str

    class Config:
        env_prefix = "MQ_"


class SchedulerSettings(BaseSettings):
    max_weight: int
    default_weight: int
    warning_weight: int

    merge_interval: int

    tmpfs_size: int

    class Config:
        env_prefix = "SCHEDULER_"


class ServerSettings(BaseSettings):
    host: str
    port: str

    class Config:
        env_prefix = "SERVER_"


class APIEndpointSettings(BaseSettings):
    starter: AnyHttpUrl

    class Config:
        env_prefix = "API_URL_"


class APISettings(BaseSettings):
    client_module: str = Field(regex=r"^aiohttp$")
    endpoints: APIEndpointSettings

    class Config:
        env_prefix = "API_"


class AppSettings(BaseModel):
    api: APISettings
    environment: EnvironmentSettings
    message_queue: MessageQueueSettings
    collections: CollectionSettings
    database: DatabaseSettings
    scheduler: SchedulerSettings
    server: ServerSettings


_app_settings = None


def get_app_settings() -> AppSettings:
    global _app_settings

    if _app_settings is None:
        _app_settings = AppSettings(
            database=DatabaseSettings(),
            collections=CollectionSettings(),
            message_queue=MessageQueueSettings(queues=MessageQueues()),
            api=APISettings(endpoints=APIEndpointSettings()),
            environment=EnvironmentSettings(),
            scheduler=SchedulerSettings(),
            server=ServerSettings(),
        )

    return _app_settings
