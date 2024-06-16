import sqlite3
import os.path

from .currencies_json_processor import get_currencies_from_json
import app.utils.rates_obtaining_from_cbr_website as cbr

pkg_dir = os.path.dirname(__file__)
currencies_in_json_path = os.path.join(pkg_dir, 'currency-format.json')


def create_db(path):
    assert not os.path.exists(path), f'File {path} already exists'

    connection = sqlite3.connect(path)
    curs = connection.cursor()
    sql = open(os.path.join(pkg_dir, 'currency_db_creation.sql')).read()

    curs.execute(sql)


def populate_currencies_from_json(db_path, json_path=currencies_in_json_path, processor=get_currencies_from_json):
    """
    Populates currency table in DB from json.
    Processor is responsible for doing all the necessary job to get the iterable with (code, full_name, sign) tuples
    from json file, specified by json_path.
    """
    assert os.path.exists(db_path), f'No DB file specified by {db_path} path. First do create_db().'

    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    currencies = processor(json_path)

    cursor.executemany('INSERT INTO currency(code, full_name, currency_sign) VALUES (?, ?, ?)', currencies)


def populate_rates(db_path, rates_fetcher):

    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    rates = cbr.obtain_rates('https://cbr.ru/currency_base/daily/')

    sql = '''
        WITH currencies_ids AS (
        SELECT b.currency_id as b, t.currency_id as t
        FROM exchange_rates
        JOIN currency b ON (b.currency_id = base_currency_id) 
        JOIN currency t ON (t.currency_id = target_currency_id)
        WHERE b.code = ? AND t.code = ?
        )
        INSERT INTO exchange_rates(base_currency_id, target_currency_id, rate) 
        VALUES (currencies_ids.b, currencies_ids.t, ?)
        '''

    cursor.executemany(sql, rates)








