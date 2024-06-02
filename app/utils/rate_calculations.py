from itertools import combinations
from dataclasses import dataclass
from typing import Sequence


@dataclass
class CurrencyRate:
    base_currency_code: str
    target_currency_code: str
    units: int
    rate: int | float

    @property
    def reduced_rate(self):

        return self.rate/self.units

    @property
    def reciprocal_rate(self):

        return 1/self.rate

    @property
    def r_reciprocal_rate(self):

        return self.units/self.rate


def calculate_rate_depending_on_base_rates(target1_to_base_rate: float | int, target2_to_base_rate: float | int):

    return target1_to_base_rate/target2_to_base_rate


def complete_building_set_of_rates(rates: Sequence[CurrencyRate]) -> Sequence[CurrencyRate]:
    # takes set of rates, completes building rates for items, which both have rates to common item
    yield from rates
    combos = combinations(rates, 2)
    for rate1, rate2 in combos:
        if rate1.target_currency_code == rate2.target_currency_code:
            new_rate = CurrencyRate(rate1.base_currency_code, rate2.base_currency_code, 1,
                                    calculate_rate_depending_on_base_rates(rate1.reduced_rate, rate2.reduced_rate))
            yield new_rate
