import unittest
import sqlite3
import datetime
import configparser

import app
from app.data_updates import CurrencyRatesUpdater
from app.data_objects import Currency
from app.utils.rates_obtaining_from_cbr_website import obtain_rates

mock_db_conn = sqlite3.connect(':memory:')
cur = mock_db_conn.cursor()
cur.executescript(open('../init/currency_db_creation.sql').read())

cp = configparser.ConfigParser()
cp.read('../configs/info_source_dbtable.ini')
db_details = {k: v for k, v in cp['schema'].items()}


cur.execute(
    'insert into rates_info_source(src_path, days_valid) VALUES (?, ?)',
    ('https://www.cbr.ru/currency_base/daily/', 1)
)
cur.executemany(
    'insert into currency(code, full_name, currency_sign) values (?, ?, ?)',
    (('USD', 'name', 'sign'), ('RUB', 'name', 'sign'))
)

cur.execute(
    'insert into exchange_rates(base_currency_id, target_currency_id, rate) values (?, ?, ?)',
    (1, 2, 96.7)
)

updater = CurrencyRatesUpdater(
    mock_db_conn, 1, obtain_rates, app.update_exchange_rate, db_details)

app.main.set_connection(mock_db_conn)


class CurrencyRatesUpdaterTest(unittest.TestCase):

    def test_UpdatesDemandChecker(self):
        cur.execute('update rates_info_source set last_appeal=? where source_id=1', ((datetime.date.today()),))
        self.assertEqual(updater.update_is_needed(), False)

        cur.execute(
            'update rates_info_source set last_appeal=? where source_id=1',
            ((datetime.date.today()-datetime.timedelta(days=1)),)
        )

        check = updater.update_is_needed()

        self.assertEqual(check, True)

    def test_UpdateRates(self):
        url = cur.execute('select src_path from rates_info_source where source_id = 1').fetchone()[0]
        rates = obtain_rates(url)

        rate = None
        for rateob in rates:
            if rateob.base_currency_code == 'USD' and rateob.target_currency_code == 'RUB':
                rate = rateob.rate
        if not rate:
            raise AssertionError('Rate not found')

        updater.update(on_nonexist_exc=app.main.NoRecordToModify)

        updated_er = cur.execute('select rate from exchange_rates where exchange_rate_id = 1').fetchone()[0]
        self.assertEqual(updated_er, rate)
        # date of last appeal is inserted
        self.assertEqual(
            cur.execute('select last_appeal from rates_info_source where source_id = 1').fetchone()[0],
            datetime.date.today().isoformat()
        )

if __name__ == '__main__':
    unittest.main()
