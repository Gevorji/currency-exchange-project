import sqlite3
from urllib.request import urlopen

from app.data_objects import CurrencyRate

DB_NAME = 'currencydb.db'

db_connection = sqlite3.connect(DB_NAME)
db_cursor = db_connection.cursor()


def get_all_currencies():

    res = db_cursor.execute('SELECT * FROM currency').fetchall()

    return res


def get_currency_by_id(_id):

    res = db_cursor.execute('SELECT * FROM currency WHERE currency_id=?', (_id,)).fetchone()

    return res


def add_currency(currency_data: tuple):

    sql = '''
    INSERT INTO currency(code, full_name, currency_sign) VALUES (?,?,?)
    RETURNING *
    '''

    res = db_cursor.execute(sql, currency_data).fetchall()
    db_connection.commit()

    return res


def get_exchange_rates():

    res = db_cursor.execute('''
    SELECT * FROM exchange_rates
    JOIN currency ON base_currency_id
    ''').fetchall()

    return res


def get_exchange_rate_for_pair(currency1, currency2):

    res = db_cursor.execute('SELECT ')


def get_resource_from_web_using_http(url: str):

    return urlopen(url).read()


def init_insert_currency_rates(obtainer_func, *, force=False):
    if not force:
        r = db_cursor.execute('DELETE FROM exchange_rates')
    db_cursor.execute('DELETE FROM exchange_rates')
    rates = tuple(obtainer_func())

    db_cursor.executemany('INSERT INTO exchange_rates(base_currency_id, target_currency_id, rate) VALUES (?, ?, ?)',
                          rates)


def update_rate(rate_data: CurrencyRate):
    sql = '''
    UPDATE exchange_rates SET rate=?, info_source=?
    WHERE base_currency_id = (SELECT currency_id FROM currency WHERE code=?) AND 
          target_currency_id = (SELECT currency_id FROM currency WHERE code=?)
    '''

    db_cursor.execute(sql, (rate_data.rate, rate_data.info_source,
                            rate_data.base_currency_code, rate_data.target_currency_code))

def add_rate(rated_data: CurrencyRate): pass