from dataclasses import dataclass, field
from .FieldValidizer import FieldValidizer
import re


@dataclass
class CurrencyRate(FieldValidizer):
    id: int | None
    base_currency_code: str | None
    target_currency_code: str | None
    units: int | None
    rate: int | float | None
    info_source: int | None

    __validations = {
        'target_currency_code': lambda v: bool(re.fullmatch('[A-Z]{3}', v)) if v is not None else False,
        'base_currency_code': lambda v: bool(re.fullmatch('[A-Z]{3}', v)) if v is not None else False
    }

    def __post_init__(self):
        self._validize_fields()

    @property
    def reduced_rate(self):

        return self.rate/self.units

    @property
    def reciprocal_rate(self):

        return 1/self.rate

    @property
    def r_reciprocal_rate(self):

        return self.units/self.rate

