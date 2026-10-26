from dataclasses import dataclass


@dataclass(frozen=True)
class Requirement:
    id: str
    text: str


@dataclass(frozen=True)
class Finding:
    code: str
    start: int
    end: int
    message: str
