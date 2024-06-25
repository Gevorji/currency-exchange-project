import unittest
import app
from app.data_objects import Currency


class ExchangeCountTest(unittest.TestCase):

    def test_countExchange(self):
        app.get_exchange_rate(Currency(None, 'RUB', None, None))


if __name__ == '__main__':
    unittest.main()
