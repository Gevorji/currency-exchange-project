import re
from dataclasses import dataclass
from .FieldValidizer import FieldValidizer


@dataclass
class Currency(FieldValidizer):
    id: int | None
    code: str | None
    full_name: str | None
    sign: str | None

    __validations = {
                     'code': lambda v: bool(re.fullmatch('[A-Z]{3}', v)) if v is not None else True,
                    }

    def __post_init__(self):
        self._validize_fields()
