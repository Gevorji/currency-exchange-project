from dataclasses import dataclass, field


@dataclass
class CurrencyRate:
    id: int | None
    base_currency_code: str | None
    target_currency_code: str | None
    units: int | None
    rate: int | float | None
    info_source: int | None

    @property
    def reduced_rate(self):

        return self.rate/self.units

    @property
    def reciprocal_rate(self):

        return 1/self.rate

    @property
    def r_reciprocal_rate(self):

        return self.units/self.rate

