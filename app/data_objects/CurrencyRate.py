from dataclasses import dataclass, field


@dataclass
class CurrencyRate:
    id: int | None = field(default=None)
    base_currency_code: str | None = field(default=None)
    target_currency_code: str | None = field(default=None)e
    units: int | None = field(default=None)
    rate: int | float | None = field(default=None)
    info_source: int | None = field(default=None)

    @property
    def reduced_rate(self):

        return self.rate/self.units

    @property
    def reciprocal_rate(self):

        return 1/self.rate

    @property
    def r_reciprocal_rate(self):

        return self.units/self.rate

