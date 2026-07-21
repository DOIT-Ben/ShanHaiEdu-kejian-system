"""Stable errors exposed by the isolated PPT rendering core."""


class PptRenderingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
