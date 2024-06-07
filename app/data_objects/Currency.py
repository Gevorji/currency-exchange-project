from dataclasses import dataclass


@dataclass
class Currency:
    id: int | None = None
    code: str
    full_name: str
    sign: str
