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

        # assuming that rate is given for 1 unit if units field is None
        if self.units is None and self.rate:
            self.units = 1

    @property
    def reduced_rate(self):

        if self.rate:
            if self.units is None:
                return self.rate
        else:
            return None
        return self.rate/self.units

    @property
    def reciprocal_rate(self):

        return 1/self.rate if self.rate else None

    @property
    def r_reciprocal_rate(self):

        if self.rate:
            if self.units is None:
                return 1/self.rate
        else:
            return None

        return self.units/self.rate

