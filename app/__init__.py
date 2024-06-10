import json
import sqlite3
from functools import wraps

from main import (get_all_currencies, get_all_exchange_rates, get_currency,
                  get_exchange_rate, update_currency, update_exchange_rate,
                  add_currency, add_exchange_rate, count_exchange, set_connection)

from data_updates import CurrencyRatesUpdater

db_specs = json.load(open('dbspecs.json'))

connection = sqlite3.connect(db_specs['db_fname'])

set_connection(connection)


def wrapper_for_transaction(db_procedure):
    @wraps(db_procedure)
    def transaction_wrapper(*args, **kwargs):
        with connection:
            res = db_procedure(*args, **kwargs)
        return res
    return



