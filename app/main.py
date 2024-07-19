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
    'id': 'exchange_rate_id',
    'info_source': 'source_id'
}

FIND_RATE_BY_RECIPROCAL = 0b001
FIND_RATE_BY_COMMON_TARGET = 0b010

RATES_VAL_PRECISION = 4


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

    identity = dict(id=params.get('id'), code=params.get('code'))
    identity = dict_remove_none_val_items(identity)

    substitute_keys(identity, CURRENCY_FIELDS_TO_DB_MAP)

    assert identity, 'No identity fields in data objects to make update'

    sql = 'SELECT * FROM currency WHERE ' + build_sql_query_params_line(identity, ' AND ')

    rec = db_cursor.execute(sql, identity).fetchone()

    return Currency(*rec) if rec else None


def update_currency(currency: Currency):
    """ERRORS:
    - no such currency in DB (OperationalError)
    - value is too big (DataError)
    - value is not valid
    """
    params = dict_remove_none_val_items(asdict(currency))

    assert params, 'Data object with empty fields were given'

    identity = dict_remove_none_val_items(dict(id=params.pop('id', None), code=params.pop('code', None)))

    assert identity, 'No identity fields in data object to make update'

    substitute_keys(params, CURRENCY_FIELDS_TO_DB_MAP)
    substitute_keys(identity, CURRENCY_FIELDS_TO_DB_MAP)

    params_line = build_sql_query_params_line(identity, ' AND ')

    cur_exists = db_cursor.execute('SELECT 1 FROM currency WHERE ' + params_line, identity).fetchone()
    if not cur_exists:
        raise NoRecordToModify(f'No record corresponding to {currency}')

    update_params_line = build_sql_query_params_line(
        dict(full_name=params.get('full_name'), currency_sign=params.get('currency_sign')), ', '
    )

    if not params:
        raise RequiredFieldAbsent('Full name or currency must be given to update')

    sql = 'UPDATE currency SET ' + build_sql_query_params_line(params, ', ') + \
          ' WHERE ' + params_line + ' RETURNING *'
    params.update(identity)

    rec = db_cursor.execute(sql, params).fetchone()

    return Currency(*rec)


def add_currency(currency: Currency):
    """ERRORS:
    - currency might already exist (IntegrityError)
    """
    sql = 'INSERT INTO currency(code, full_name, currency_sign) VALUES (?,?,?) RETURNING *'
    # TODO: is RETURNING * statement returning all field of the inserted row?

    try:
        res = db_cursor.execute(sql, (currency.code, currency.full_name, currency.sign)).fetchone()
    except sqlite3.Error as e:
        if e.sqlite_errorcode == 2067:
            raise RecordOfSuchIdentityExists(f'Record with the same identity as {currency} already exists in database.')
        elif e.sqlite_errorcode == 1299:
            raise RequiredFieldAbsent(f'Code, full name and sign of new currency must be given')
        else:
            raise

    return Currency(*res)


def get_all_exchange_rates():
    res = db_cursor.execute(
        '''
    SELECT exchange_rate_id, b.code, t.code, rate, source_id
    FROM exchange_rates
    JOIN currency b ON (b.currency_id = base_currency_id) 
    JOIN currency t ON (t.currency_id = target_currency_id)
    ''').fetchall()

    return tuple(CurrencyRate(*rec[:3], 1, *rec[3:]) for rec in res)


def get_exchange_rate(rate: CurrencyRate, *, strategy: int = 0):
    """ERRORS:
    - no idenitity fields were given
    - no such rate in DB
    """
    params = dict_remove_none_val_items(asdict(rate))

    by_id = 'id' in params

    by_cur_codes = 'base_currency_code' in params and 'target_currency_code' in params

    assert by_id or by_cur_codes, ('No any identity set of fields in data object to fetch data. '
                                   'Either id of rate or base+target currencies should be given')

    identity = dict(id=params.get('id')) if by_id else dict(base_currency_code=params.get('base_currency_code'),
                                                            target_currency_code=params.get('target_currency_code'))

    substitute_keys(params, CURRENCY_RATE_FIELDS_TO_DB_MAP)
    substitute_keys(identity, CURRENCY_RATE_FIELDS_TO_DB_MAP)

    if by_id:
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

    if res:
        return CurrencyRate(*res[:3], 1, *res[3:])

    if not by_cur_codes and strategy != 0:
        raise AssertionError('Cant use any tricky fetching strategies when no both base and target codes were given')

    if FIND_RATE_BY_RECIPROCAL & strategy == FIND_RATE_BY_RECIPROCAL:
        res = get_exchange_rate(CurrencyRate(None, identity['target_currency_code'],
                                             identity['base_currency_code'], None, None, None))
        if res:
            rate.units = 1
            rate.rate = round(res.reciprocal_rate, RATES_VAL_PRECISION)
            return rate

    if FIND_RATE_BY_COMMON_TARGET & strategy == FIND_RATE_BY_COMMON_TARGET:
        ids = db_cursor.execute(
            '''
            SELECT currency_id
            FROM currency
            WHERE code IN (?, ?)
            ''', (params['base_currency_code'], params['target_currency_code'])).fetchall()

        if len(ids) != 2:
            return None

        base_id, target_id = tuple(rec[0] for rec in ids)

        sql = '''
            WITH common_cur AS 
            (SELECT target_currency_id AS id
            FROM exchange_rates
            WHERE base_currency_id = ?
            INTERSECT 
            SELECT target_currency_id AS id
            FROM exchange_rates
            WHERE base_currency_id = ?
            LIMIT 1)
            SELECT rate
            FROM exchange_rates
            WHERE base_currency_id = ? AND target_currency_id = (SELECT * FROM common_cur)
            UNION ALL
            SELECT rate
            FROM exchange_rates
            WHERE base_currency_id = ? AND target_currency_id = (SELECT * FROM common_cur)
            '''

        res = tuple(rec[0] for rec in db_cursor.execute(
            sql, (base_id, target_id, base_id, target_id)).fetchall())

        if res:
            res = round(res[0] / res[1], RATES_VAL_PRECISION)
            return CurrencyRate(None, params['base_currency_code'], params['target_currency_code'], 1, res, None)

    return None


def update_exchange_rate(rate: CurrencyRate):
    """ERRORS:
    - no identity fields were given
    - value is too big (DataError)
    - value is not valid
    """
    target_fields = ('id', 'base_currency_code', 'target_currency_code', 'rate', 'info_source')
    params = {k: v for k, v in asdict(rate).items() if k in target_fields}

    identity = (dict_remove_none_val_items(dict(id=params.get('id'))) or
                dict_remove_none_val_items(dict(base_currency_code=params.get('base_currency_code'),
                                                target_currency_code=params.get('target_currency_code'))))

    any_identity_set_is_given = ('id' in identity or
                                 ('base_currency_code' in identity and 'target_currency_code' in identity))


    assert any_identity_set_is_given, ('No any identity set of fields in data object to fetch data. '
                                       'Either id of rate or base+target currencies should be given')

    if not params.get('rate') and not params.get('info_source'):
        raise RequiredFieldAbsent('Rate value or source_id must be given to update')

    params['rate'] = rate.reduced_rate

    substitute_keys(params, CURRENCY_RATE_FIELDS_TO_DB_MAP)
    substitute_keys(identity, CURRENCY_RATE_FIELDS_TO_DB_MAP)

    sql_query_params_line = build_sql_query_params_line(
        dict_remove_none_val_items(dict(rate=params.get('rate'), source_id=params.get('source_id'))), ', '
    )

    rate_exists = get_exchange_rate(rate)
    if not rate_exists:
        raise NoRecordToModify(f'No rate that corresponds to {rate}')

    if len(identity) == 1:
        cte_param_line = build_sql_query_params_line(identity, '')
        sql = 'UPDATE exchange_rates SET ' + sql_query_params_line + ' WHERE ' + cte_param_line + ' RETURNING *'
    else:
        cte_param_line = 'b.code = :base_currency_code AND t.code = :target_currency_code'
        cte = '''
            WITH currencies_ids AS (
                SELECT b.currency_id as b, t.currency_id as t
                FROM currency b
                JOIN currency t ON ''' + cte_param_line + ')\n'

        sql = cte + '''
            UPDATE exchange_rates SET
            ''' + sql_query_params_line + '''
            WHERE base_currency_id = (SELECT b FROM currencies_ids) AND target_currency_id = (SELECT t FROM currencies_ids)
            RETURNING *
            '''

    try:
        res = db_cursor.execute(sql, params).fetchone()
    except sqlite3.Error as e:
        if e.sqlite_errorcode == 787:
            raise QueryError('Foreign key constraint failed')
        raise

    return CurrencyRate(res[0], params['base_currency_code'], params['target_currency_code'], 1, *res[3:])


def add_exchange_rate(rate: CurrencyRate):
    """ERRORS:
    - such rate might already exist (IntegrityError)
    - any of the required fields might be none (OperationalError)
    """
    target_fields = ('base_currency_code', 'target_currency_code', 'rate', 'info_source')
    params = {k: v for k, v in asdict(rate).items() if k in target_fields}
    params['rate'] = rate.reduced_rate

    identity = dict_remove_none_val_items(dict(base_currency_id=params.get('base_currency_code'),
                                               target_currency_id=params.get('target_currency_code')))

    assert len(identity) == 2, 'Base and target currency codes should be given'

    substitute_keys(params, CURRENCY_RATE_FIELDS_TO_DB_MAP)

    cte = '''
        WITH currencies_ids AS (
            SELECT b.currency_id as b, t.currency_id as t
            FROM currency b
            JOIN currency t ON b.code = :base_currency_code and t.code = :target_currency_code 
        )
        '''

    sql = cte + '''
        INSERT INTO exchange_rates(base_currency_id, target_currency_id, rate, source_id) 
        SELECT currencies_ids.b, currencies_ids.t, :rate, :source_id
        FROM currencies_ids
        RETURNING *'''

    try:
        res = db_cursor.execute(sql, params).fetchone()
    except sqlite3.Error as e:
        if e.sqlite_errorcode == 2067:
            raise RecordOfSuchIdentityExists(f'Record with the same identity as {rate} already exists in database.')
        elif e.sqlite_errorcode == 1299:
            raise RequiredFieldAbsent(f'Rate must be given')
        elif e.sqlite_errorcode == 787:
            raise QueryError('Foreign key constraint failed')
        else:
            raise

    if res:
        return CurrencyRate(res[0], params['base_currency_code'], params['target_currency_code'], 1, *res[3:])
    else:
        return None


class QueryError(Exception):
    pass


class NoRecordToModify(QueryError):
    pass


class RecordOfSuchIdentityExists(QueryError):
    pass


class BadIdentity(QueryError):
    pass


class RequiredFieldAbsent(QueryError):
    pass
