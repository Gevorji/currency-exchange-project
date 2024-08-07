from dataclasses import dataclass

from app.data_objects import Currency


@dataclass
class ExchangeRate:
    id: int
    baseCurrency: Currency
    targetCurrency: Currency
    rate: float | int


@dataclass
class ConvertedExchangeRate:
    baseCurrency: Currency
    targetCurrency: Currency
    rate: float | int
    amount: float | int
    convertedAmount: float | int
