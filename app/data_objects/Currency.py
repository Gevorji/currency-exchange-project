from dataclasses import dataclass


@dataclass
class Currency:
    id: int | None
    code: str | None
    full_name: str | None
    sign: str | None
