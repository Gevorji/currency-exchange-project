import sqlite3

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


