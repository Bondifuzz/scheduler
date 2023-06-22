class ExternalAPIError(Exception):
    pass


class EAPIClientError(ExternalAPIError):
    pass


class EAPIServerError(ExternalAPIError):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(code, message)

    @property
    def code(self) -> int:
        return self.args[0]

    @property
    def message(self) -> str:
        return self.args[1]

    def __str__(self) -> str:
        return f"[{self.code:02}] {self.message}"


class EAPIResponseParseError(ExternalAPIError):
    def __init__(self):
        super().__init__("Failed to parse server response")
