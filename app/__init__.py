import os
from configparser import ConfigParser
import sqlite3
from functools import wraps
from typing import Callable

from app import main
from app.main import (get_all_currencies, get_all_exchange_rates, get_currency,
                      get_exchange_rate, update_currency, update_exchange_rate,
                      add_currency, add_exchange_rate)

from app.data_updates import CurrencyRatesUpdater

COMMIT_IF_SUCCESS = True

pkg_dir = os.path.dirname(__file__)

connection = None

configs = ConfigParser()

configs.read(os.path.join(pkg_dir, r'configs\dbconfigs.ini'))


def connect_db(db_path):
    global connection
    # have to disable same thread checking because apparently the majority of well known wsgi servers
    # (like waitress, for example) run application in another thread, which causes sqlite API to raise an error
    # connection = sqlite3.connect(db_path, isolation_level='DEFERRED', check_same_thread=False)
    connection = sqlite3.connect(db_path, check_same_thread=False)
    main.set_connection(connection)
    main.db_cursor.execute('PRAGMA foreign_keys(1)')


connect_db(os.path.join(pkg_dir, configs['DEFAULT']['db_fname']))


def wrapper_for_transaction(db_procedure):
    @wraps(db_procedure)
    def transaction_wrapper(*args, **kwargs):
        global connection
        global COMMIT_IF_SUCCESS
        try:
            connection.execute('BEGIN')
            res = db_procedure(*args, **kwargs)
            if COMMIT_IF_SUCCESS:
                connection.execute('COMMIT')
        except:
            connection.execute('ROLLBACK')
            raise

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

