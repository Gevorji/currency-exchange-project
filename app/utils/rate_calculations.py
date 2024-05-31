from itertools import combinations
from dataclasses import dataclass
from typing import Sequence

@dataclass
class CurrencyRate:
    base_currency_code: str
    target_currency_code: str
    rate: int | float


def get_item_pairs_from_set(items):

    return combinations(items, 2)


def calculate_rate_depending_on_base_rates(target1_to_base_rate: float | int, target2_to_base_rate: float | int):

    return target1_to_base_rate/target2_to_base_rate


def complete_building_set_of_rates(rates: Sequence[CurrencyRate]) -> Sequence[CurrencyRate]:
    # takes set of rates, completes building rates for items, which both have rates to common item
    pass