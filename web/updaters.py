import os.path
import sqlite3
from configparser import ConfigParser

import app
from app.data_updates import CurrencyRatesUpdater
from app.utils import rates_obtaining_from_cbr_website as cbr


def get_er_updaters():
    objs = []
    for updp in _updaters_params:
        objs.append(
            CurrencyRatesUpdater(app.connection, *updp)
        )
    return tuple(objs)


p = ConfigParser()
p.read(os.path.join(app.pkg_dir, r'configs\info_source_dbtable.ini'))
table_schema = {k: v for k, v in p['schema'].items()}

_updaters_params = [
    (1, cbr.obtain_rates, app.update_exchange_rate, table_schema)
]