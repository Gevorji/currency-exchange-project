import sqlite3
from functools import partial
from urllib.request import urlopen
from dataclasses import asdict
from typing import Callable

from app.data_objects import CurrencyRate, Currency

CONNECTION: sqlite3.Connection | None = None
db_cursor: sqlite3.Cursor | None = None

CURRENCY_FIELDS_TO_DB_MAP = {
    'id': 'currency_id',
    'sign': 'currency_sign'
}

CURRENCY_RATE_FIELDS_TO_DB_MAP = {
    'id': 'exchange_rate_id'
}


def set_connection(db_connection: sqlite3.Connection):
    global CONNECTION
    global db_cursor
    CONNECTION = db_connection
    db_cursor = CONNECTION.cursor()


def build_sql_query_params_line(params: dict, joiner):
    return joiner.join(key + f' = :{key}' for key in params.keys())


def filter_dict(key_filter: Callable | None, value_filter: Callable | None, d):
    if key_filter is None:
        key_filter = lambda k: bool(k)
    if value_filter is None:
        value_filter = lambda v: bool(v)

    return {k: v for k, v in d.items() if key_filter(k) and value_filter(v)}


dict_remove_none_val_items = partial(filter_dict, None, lambda v: v is not None)


def substitute_keys(d, subs: dict):
    new_d = []
    removal = []
    for k in d:
        new_key = subs.get(k)
        if new_key:
            new_d.append((subs[k], d[k]))
            removal.append(k)
    for k in removal:
        del d[k]
    d.update(dict(new_d))


def get_all_currencies():
    res = db_cursor.execute('SELECT * FROM currency').fetchall()

    return tuple(Currency(*rec) for rec in res)


def get_currency(currency: Currency):
    """ERRORS:
    - no identity fields were given
    - no such currency in DB
    """
    params = dict_remove_none_val_items(asdict(currency))

    identity = dict(id=params.get('currrency_id'), code=params.get('code'))

    substitute_keys(identity, CURRENCY_FIELDS_TO_DB_MAP)

    assert identity, 'No identity fields in data objects to make update'

    sql = 'SELECT * FROM currency WHERE' + build_sql_query_params_line(identity, ' AND ')

    rec = db_cursor.execute(sql, params).fetchone()

    return Currency(*rec)


def update_currency(currency: Currency):
    """ERRORS:
    - no such currency in DB (OperationalError)
    - value is too big (DataError)
    - value is not valid
    """
    params = dict_remove_none_val_items(asdict(currency))
    substitute_keys(params, CURRENCY_FIELDS_TO_DB_MAP)

    assert params, 'Data object with empty fields were given'

    identity = dict_remove_none_val_items(dict(id=params.pop('id', None), code=params.pop('code', None)))

    assert identity, 'No identity fields in data object to make update'

    sql = 'UPDATE currency SET ' + build_sql_query_params_line(identity, ', ') + \
          ' WHERE ' + build_sql_query_params_line(params, ' AND ') + ' RETURNING *'
    params.update(identity)

    rec = db_cursor.execute(sql, params)

    return Currency(*rec)


def add_currency(currency: Currency):
    """ERRORS:
    - currency might already exist (IntegrityError)
    """
    sql = 'INSERT INTO currency(code, full_name, currency_sign) VALUES (?,?,?) RETURNING *'
    # TODO: is RETURNING * statement returning all field of the inserted row?

    res = db_cursor.execute(sql, (currency.code, currency.full_name, currency.sign)).fetchone()

    return res


def get_all_exchange_rates():
    res = db_cursor.execute(
        '''
    SELECT exchange_rate_id, b.code, t.code, rate
    FROM exchange_rates
    JOIN currency b ON (b.currency_id = base_currency_id) 
    JOIN currency t ON (t.currency_id = target_currency_id)
    ''').fetchall()

    return tuple(CurrencyRate(*rec) for rec in res)


def get_exchange_rate(rate: CurrencyRate):
    """ERRORS:
    - no idenitity fields were given
    - no such rate in DB
    """
    params = dict_remove_none_val_items(asdict(rate))

    identity = (dict_remove_none_val_items(dict(id=params.get('id'))) or
                dict_remove_none_val_items(dict(base_currency_id=params.get('base_currency_code'),
                                                target_currency_id=params.get('target_currency_code'))))

    any_identity_set_is_given = ('id' in identity or
                                 ('base_currency_code' in identity and 'target_currency_code' in identity))

    assert any_identity_set_is_given, ('No any identity set of fields in data object to fetch data. '
                                       'Either id of rate or base+target currencies should be given')

    substitute_keys(identity, CURRENCY_RATE_FIELDS_TO_DB_MAP)

    if len(identity) == 1:
        param_line = build_sql_query_params_line(identity, '')
    else:
        param_line = 'b.code = :base_currency_code AND t.code = :target_currency_code'

    sql = '''
        SELECT exchange_rate_id, b.code, t.code, rate, source_id
        FROM exchange_rates
        JOIN currency b ON (b.currency_id = base_currency_id) 
        JOIN currency t ON (t.currency_id = target_currency_id)
        WHERE ''' + param_line

    res = db_cursor.execute(sql, identity).fetchone()

    return CurrencyRate(*res[:3], 1, res[3], res[-1]) if res else None


def update_exchange_rate(rate: CurrencyRate):
    """ERRORS:
    - no identity fields were given
    - value is too big (DataError)
    - value is not valid
    """
    params = dict_remove_none_val_items(asdict(rate))

    identity = (dict_remove_none_val_items(dict(id=params.get('id'))) or
                dict_remove_none_val_items(dict(base_currency_id=params.get('base_currency_code'),
                                                target_currency_id=params.get('target_currency_code'))))

    any_identity_set_is_given = ('id' in identity or
                                 ('base_currency_code' in identity and 'target_currency_code' in identity))

    assert any_identity_set_is_given, ('No any identity set of fields in data object to fetch data. '
                                       'Either id of rate or base+target currencies should be given')

    substitute_keys(params, CURRENCY_RATE_FIELDS_TO_DB_MAP)
    substitute_keys(identity, CURRENCY_RATE_FIELDS_TO_DB_MAP)

    if len(identity) == 1:
        cte_param_line = build_sql_query_params_line(identity, '')
    else:
        cte_param_line = 'b.code = :base_currency_code AND t.code = :target_currency_code'

    cte = '''
    WITH currencies_ids AS (
    SELECT b.currency_id as b, t.currency_id as t
    FROM exchange_rates
    JOIN currency b ON (b.currency_id = base_currency_id) 
    JOIN currency t ON (t.currency_id = target_currency_id)
    WHERE ''' + cte_param_line + ')\n'

    sql = cte + 'UPDATE exchange_rates SET ' + build_sql_query_params_line(params, ', ') + \
          ' WHERE base_currency_id = currencies_ids.b, target_currency_id = currencies_ids.t)'

    params.update(identity)
    res = db_cursor.execute(sql, params).fetchone()

    return res


def add_exchange_rate(rate: CurrencyRate):
    """ERRORS:
    - such rate might already exist (IntegrityError)
    - any of the required fields might be none (OperationalError)
    """
    target_fields = ('base_currency_code', 'target_currency_code', 'rate', 'source_id')
    params = {k: v for k, v in asdict(rate).items() if k in target_fields}
    params['rate'] = rate.reduced_rate

    identity = dict_remove_none_val_items(dict(base_currency_id=params.get('base_currency_code'),
                                               target_currency_id=params.get('target_currency_code')))

    assert len(identity) == 2, ('No any identity set of fields in data object to fetch data. '
                                'Either id of rate or base+target currencies should be given')

    substitute_keys(params, CURRENCY_RATE_FIELDS_TO_DB_MAP)

    cte = '''
        WITH currencies_ids AS (
        SELECT b.currency_id as b, t.currency_id as t
        FROM exchange_rates
        JOIN currency b ON (b.currency_id = base_currency_id) 
        JOIN currency t ON (t.currency_id = target_currency_id)
        WHERE b.code = :base_currency_code AND t.code = :target_currency_code
        '''

    sql = cte + '''
    INSERT INTO exchange_rates(base_currency_id, target_currency_id, rate) 
    VALUES (currencies_ids.b, currencies_ids.t, :rate, :source_id)
    RETURNING *'''

    res = db_cursor.execute(sql, params).fetchone()

    return CurrencyRate(*res[:3], 1, *res[3:])


def count_exchange(fromcur: Currency, tocur: Currency, amount):
    base_cur = get_currency(fromcur)
    target_cur = get_currency(tocur)
    rate = get_exchange_rate(CurrencyRate(None, base_cur.code, target_cur.code, None, None, None))

    # base_cur_identity = fromcur.code or fromcur.id
    # target_cur_identity = tocur.code or tocur.id

    # assert base_cur_identity and target_cur_identity, 'No identity in one or more given objects'
    #
    # if base_cur_identity == fromcur.id:
    #     base_cur_identity = db_cursor.execute('SELECT code FROM currency WHERE currency_id = ?', (fromcur.id,))
    # if target_cur_identity == tocur.id:
    #     target_cur_identity = db_cursor.execute('SELECT code FROM currency WHERE currency_id = ?', (tocur.id,))

    # rate = get_exchange_rate(CurrencyRate(None, base_cur_identity, target_cur_identity, None, None, None))

    return base_cur, target_cur, rate, rate.rate * amount



