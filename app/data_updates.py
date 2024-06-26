import sqlite3
import datetime
from typing import Callable

from app.data_objects import CurrencyRate


def adapt_date_iso(val):
    return val.isoformat()


sqlite3.register_adapter(datetime.date, adapt_date_iso)


class CurrencyRatesUpdater:
    __instances = []
    """
    Provides functionality for keeping currency rates up-to-date in application's database
    """
    __db_details_specs = ('table_name', '', 'pk_field',  'last_appeal_data_field', 'days_valid_field', 'path_field',
                          'type_field')

    def __init__(self, conn, source_id, fetcher_procedure: Callable, update_interface: Callable, db_details: dict):
        self.__update_interface = update_interface
        self.__connection: sqlite3.Connection = conn
        self.__db_cursor: sqlite3.Cursor = self.__connection.cursor()

        assert source_id not in [inst.source_id for inst in getattr(self, f'_{self.__class__.__name__}__instances')], \
            'The updater on this source has been set already'

        assert set(self.__db_details_specs) & set(db_details.keys()) == set(self.__db_details_specs), \
            'One of the required database specification parameters is missing'

        assert self.__db_cursor.execute('SELECT * FROM :table_name WHERE :pk_field = :source_id').fetchone(), \
            f'No source in table with {source_id=}'

        self.__db_details = db_details
        self.source_id = source_id
        self.fetch_data = fetcher_procedure

        getattr(self, f'_{self.__class__.__name__}__instances').append(self)

    def update_is_needed(self):
        details = self.__db_details
        res = self.__db_cursor.execute(
            'SELECT :last_appeal_data_field, :days_valid_field FROM :table_name WHERE :pk_field = :source_id', details
        ).fetchone()

        last_appeal, days_valid = datetime.date.fromisoformat(res[0]), datetime.timedelta(days=res[1])

        return True if last_appeal + days_valid <= datetime.date.today() else False

    def obtain_data(self):
        path = self.get_path_to_source()

        def preparer(rate: CurrencyRate):
            rate.info_source = self.source_id

        yield from (preparer(rate) for rate in self.fetch_data())

    def get_path_to_source(self):
        details = self.__db_details

        res = self.__db_cursor.execute('SELECT :path_field FROM :table_name WHERE :pk_field = :source_id',
                                       details).fetchone()
        return res[0]

    def update(self):

        data = self.obtain_data()

        for rate in data:
            self.__update_interface(rate)

        datestamp = datetime.date.today()
        details = self.__db_details.copy()
        details['datestamp'] = datestamp
        details['source_id'] = self.source_id
        sql = '''UPDATE :table_name SET :last_appeal_data_field = :datestamp WHERE :pk_field = :source_id'''
        self.__db_cursor.execute(sql, details)

