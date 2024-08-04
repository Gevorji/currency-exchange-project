import unittest
from dataclasses import asdict
from functools import partial

import app
from app.data_objects import CurrencyRate, Currency

app.connect_db('test.db')


app.COMMIT_IF_SUCCESS = False


def is_equal_data_objects(first: Currency | CurrencyRate, second: Currency | CurrencyRate, msg=None):
    first = asdict(first)
    second = asdict(second)

    differences = {k: (first.get(k), second.get(k)) for k in set(first.keys()) | set(second.keys())
                   if first.get(k) != second.get(k)}

    if differences:
        raise unittest.TestCase.failureException(f'Inequality: {" ".join(f"{k}: {v}" for k, v in differences.items())}')


class CurrencyCrudTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.addTypeEqualityFunc(Currency, is_equal_data_objects)

    def setUp(self) -> None:
        self.cursor = app.connection.cursor()

    def tearDown(self) -> None:
        app.connection.rollback()

    def test_getAllCurrencies(self):
        correct_result_set = tuple(Currency(*rec) for rec in self.cursor.execute('SELECT * FROM currency').fetchall())

        self.assertEqual(
            app.get_all_currencies(), correct_result_set

        )

    def test_getCurrencyByIdOrCode(self):
        correct_result_single_currency = Currency(4, 'AMD', 'Armenian Dram', 'դր.')
        self.assertEqual(app.get_currency(Currency(4, None, None, None)), correct_result_single_currency)
        self.assertEqual(app.get_currency(Currency(None, 'AMD', None, None)), correct_result_single_currency)

    def test_getNonExistingCurrency(self):
        self.assertEqual(app.get_currency(Currency(None, 'XXX', None, None)), None)
        self.assertEqual(app.get_currency(Currency(100000, None, None, None)), None)

    def test_updateCurrencyByIdOrCode(self):
        correct_result = Currency(4, 'AMD', 'Armenian Dram', 'changed')

        self.assertEqual(app.update_currency(Currency(4, None, None, 'changed')), correct_result)
        app.connection.rollback()
        self.assertEqual(app.update_currency(Currency(None, 'AMD', None, 'changed')), correct_result)

    def test_updateNonExistingCurrency(self):
        with self.assertRaises(app.main.NoRecordToModify):
            app.update_currency(Currency(None, 'XXX', None, None))

    def test_updateWithWhenNoRequiredFieldsGiven(self):
        with self.assertRaises(app.main.RequiredFieldAbsent):
            app.update_currency(Currency(1, None, None, None))

    def test_addNewCurrency(self):
        correct_result = Currency(184, 'CRY', 'new_currency', 'new_sign')

        self.assertEqual(app.add_currency(Currency(None, 'CRY', 'new_currency', 'new_sign')), correct_result)

    def test_addCurrencyWithExistingCodeOrId(self):
        with self.assertRaises(app.main.RecordOfSuchIdentityExists):
            app.add_currency(Currency(4, 'AMD', 'name', 'sign'))


class ExchangeRatesCrudTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.addTypeEqualityFunc(CurrencyRate, is_equal_data_objects)

    def setUp(self) -> None:
        self.cursor = app.connection.cursor()

    def tearDown(self) -> None:
        app.connection.rollback()

    def test_getAllRates(self):
        sql = '''
        SELECT exchange_rate_id, b.code, t.code, rate, source_id
        FROM exchange_rates
        JOIN currency b ON (b.currency_id = base_currency_id) 
        JOIN currency t ON (t.currency_id = target_currency_id)
        '''
        correct_result_set_rates = tuple(CurrencyRate(*rec[:3], 1, *rec[3:]) for rec in self.cursor.execute(
            sql).fetchall())
        self.assertEqual(app.get_all_exchange_rates(), correct_result_set_rates)

    def test_getOneRateByIdOrCode(self):
        correct_result_single_rate = CurrencyRate(1, 'AUD', 'RUB', 1, 58.0244, None)

        self.assertEqual(app.get_exchange_rate(CurrencyRate(1, 'EMP', 'EMP', None, None, None)),
                         correct_result_single_rate)
        self.assertEqual(app.get_exchange_rate(CurrencyRate(None, 'AUD', 'RUB', None, None, None)),
                         correct_result_single_rate)

    def test_getNonExistingRate(self):
        self.assertEqual(app.get_exchange_rate(CurrencyRate(None, 'BTC', 'ZAR', None, None, None)), None)

        # non-existing currencies rate fetch
        self.assertEqual(app.get_exchange_rate(CurrencyRate(None, 'ZZZ', 'XXX', None, None, None)), None)

        # non-existing rate that possibly could be found by reciprocal/common currency strategy
        self.assertEqual(app.get_exchange_rate(CurrencyRate(None, 'RUB', 'AUD', None, None, None)), None)

        # non-existing rate that couldn't be found even by reciprocal/common currency strategy
        strategy = app.main.FIND_RATE_BY_COMMON_TARGET | app.main.FIND_RATE_BY_RECIPROCAL
        self.assertEqual(app.get_exchange_rate(CurrencyRate(None, 'BTC', 'ZAR', None, None, None), strategy=strategy),
                         None)

    def test_getRateByReciprocalStrategy(self):
        correct_result_single_rate = CurrencyRate(None, 'RUB', 'AUD', 1, 0.0172, None)
        self.assertEqual(app.get_exchange_rate(CurrencyRate(None, 'RUB', 'AUD', None, None, None),
                                               strategy=app.main.FIND_RATE_BY_RECIPROCAL),
                         correct_result_single_rate)

    def test_getRateByCommonCurrencyStrategy(self):
        sql = '''
        INSERT INTO exchange_rates(base_currency_id, target_currency_id, rate)
        VALUES 
        (?, ?, ?)
        '''
        self.cursor.executemany(sql, ((181, 159, 5000), (182, 159, 890.15)))
        app.connection.commit()

        correct_result_single_rate = CurrencyRate(None, 'BTC', 'ETH', 1, round(5000 / 890.15, 4), None)
        try:
            strategy = app.main.FIND_RATE_BY_COMMON_TARGET
            self.assertEqual(app.get_exchange_rate(CurrencyRate(None, 'BTC', 'ETH', None, None, None), strategy=strategy),
                             correct_result_single_rate)
        finally:
            self.cursor.execute('DELETE FROM exchange_rates WHERE exchange_rate_id > 946')
            app.connection.commit()

    def test_updateRate(self):
        correct_result_single_rate = CurrencyRate(1, 'AUD', 'RUB', 1, 45, None)

        self.assertEqual(app.update_exchange_rate(CurrencyRate(1, 'AUD', 'RUB', 1, 45, None)),
                         correct_result_single_rate)

    def test_updateRateWhenNoRateValueIsGiven(self):
        with self.assertRaises(app.main.RequiredFieldAbsent):
            app.main.update_exchange_rate(CurrencyRate(1, 'AUD', 'RUB', 1, None, None))

    def test_updateRateWithNonExistingSource(self):
        with self.assertRaises(app.main.QueryError):
            app.main.update_exchange_rate(CurrencyRate(1, 'AUD', 'RUB', 1, 4, 2))

    def test_addRate(self):
        correct_result_single_rate = CurrencyRate(947, 'BTC', 'USD', 1, 5000, None)

        self.assertEqual(app.add_exchange_rate(CurrencyRate(None, 'BTC', 'USD', 1, 5000, None)),
                         correct_result_single_rate)
        app.connection.rollback()

        self.assertEqual(app.add_exchange_rate(CurrencyRate(None, 'BTC', 'USD', 5, 5000 * 5, None)),
                         correct_result_single_rate)

    def test_addRateForNonExistingCurrency(self):
        self.assertEqual(app.add_exchange_rate(CurrencyRate(None, 'AUD', 'XXX', 1, 4, None)), None)

    def test_addExistingRate(self):
        with self.assertRaises(app.main.RecordOfSuchIdentityExists):
            app.add_exchange_rate(CurrencyRate(None, 'AUD', 'RUB', 1, 4, None))

    def test_addRateWithNoRateValueGiven(self):
        with self.assertRaises(app.main.RequiredFieldAbsent):
            app.add_exchange_rate(CurrencyRate(None, 'BTC', 'USD', 1, None, None))


if __name__ == '__main__':
    unittest.main()
