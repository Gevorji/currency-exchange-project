import os
from configparser import ConfigParser
import sqlite3
from functools import wraps
from typing import Callable

from app.main import (get_all_currencies, get_all_exchange_rates, get_currency,
                      get_exchange_rate, update_currency, update_exchange_rate,
                      add_currency, add_exchange_rate, count_exchange, set_connection)

from app.data_updates import CurrencyRatesUpdater

pkg_dir = os.path.dirname(__file__)

configs = ConfigParser()

configs.read(open(os.path.join(pkg_dir, r'configs\dbconfigs.ini')))

connection = sqlite3.connect(configs['DEFAULT']['db_fname'])

set_connection(connection)


def connect_db(db_path):
    global connection
    connection = sqlite3.connect(db_path)
    set_connection(connection)


def wrapper_for_transaction(db_procedure):
    @wraps(db_procedure)
    def transaction_wrapper(*args, commit_if_success=True,**kwargs):
        if commit_if_success:
            with connection:
                res = db_procedure(*args, **kwargs)
        else:
            try:
                res = db_procedure(*args, **kwargs)
            except sqlite3.Error:
                connection.rollback()
        return res

    return transaction_wrapper


update_currency = wrapper_for_transaction(update_currency)
update_exchange_rate = wrapper_for_transaction(update_exchange_rate)
add_currency = wrapper_for_transaction(add_currency)
add_exchange_rate = wrapper_for_transaction(add_exchange_rate)


def get_updater(fetcher_procedure: Callable = None, source_id: int = None):
    if not fetcher_procedure and source_id:
        from app.utils.rates_obtaining_from_cbr_website import obtain_rates
        fetcher_procedure = obtain_rates
        source_id = 1
    update_interface = update_exchange_rate
    specs_cfg = ConfigParser()
    specs_cfg.read(open(r'configs\info_source_dbtable.ini'))
    db_specs = {k: v for k, v in specs_cfg['schema'].items()}

    return CurrencyRatesUpdater(connection, source_id, fetcher_procedure, update_interface, db_specs)

