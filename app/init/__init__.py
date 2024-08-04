import datetime
import sqlite3
import os.path
from functools import partial

from .currencies_json_processor import get_currencies_from_json
import app.utils.rates_obtaining_from_cbr_website as cbr

pkg_dir = os.path.dirname(__file__)
currencies_in_json_path = os.path.join(pkg_dir, 'currency-format.json')


def create_db(path):
    assert not os.path.exists(path), f'File {path} already exists'

    connection = sqlite3.connect(path)
    curs = connection.cursor()
    sql = open(os.path.join(pkg_dir, 'currency_db_creation.sql')).read()

    try:
        with connection:
            curs.executescript(sql)
    finally:
        connection.close()


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

    try:
        with connection:
            cursor.executemany('INSERT INTO currency(code, full_name, currency_sign) VALUES (?, ?, ?)', currencies)
    finally:
        connection.close()


def populate_rates(db_path, rates_fetcher=partial(cbr.obtain_rates, prepare_func=cbr.prepare_for_insertion_into_db)):
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    source_path = 'https://cbr.ru/currency_base/daily/'
    injection_date = datetime.date.today().isoformat()

    rates = rates_fetcher(source_path)

    sql = '''
        WITH currencies_ids AS (
            SELECT currency.currency_id as b, t.currency_id as t
            FROM currency
            JOIN currency t ON currency.code = ? and t.code = ? 
        )
        INSERT INTO exchange_rates(base_currency_id, target_currency_id, rate) 
        SELECT currencies_ids.b, currencies_ids.t, ?
        FROM currencies_ids
        '''

    try:
        with connection:
            cursor.executemany(sql, rates)
            cursor.execute(
                'UPDATE rates_info_source SET last_appeal = ? WHERE src_path = ?',
                (injection_date, source_path)
            )
    finally:
        connection.close()
