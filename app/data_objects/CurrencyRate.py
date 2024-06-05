from dataclasses import dataclass


@dataclass
class CurrencyRate:
    base_currency_code: str
    target_currency_code: str
    units: int
    rate: int | float
    info_source: int = None

    @property
    def reduced_rate(self):

        return self.rate/self.units

    @property
    def reciprocal_rate(self):

        return 1/self.rate

    @property
    def r_reciprocal_rate(self):

        return self.units/self.rate
