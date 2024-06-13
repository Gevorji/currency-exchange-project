from configparser import ConfigParser
import sqlite3
from functools import wraps

from app.main import (get_all_currencies, get_all_exchange_rates, get_currency,
                      get_exchange_rate, update_currency, update_exchange_rate,
                      add_currency, add_exchange_rate, count_exchange, set_connection)

from app.data_updates import CurrencyRatesUpdater

configs = ConfigParser()

configs.read(open(r'configs\dbspecs.ini'))

connection = sqlite3.connect(configs['DEFAULT']['db_fname'])

set_connection(connection)


def wrapper_for_transaction(db_procedure):
    @wraps(db_procedure)
    def transaction_wrapper(*args, **kwargs):
        with connection:
            res = db_procedure(*args, **kwargs)
        return res

    return transaction_wrapper


update_currency = wrapper_for_transaction(update_currency)
update_exchange_rate = wrapper_for_transaction(update_exchange_rate)
add_currency = wrapper_for_transaction(add_currency)
add_exchange_rate = wrapper_for_transaction(add_exchange_rate)



def get_updater(fetcher_procedure: Callable = None): pass
