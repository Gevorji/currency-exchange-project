import sqlite3
import datetime
import sys
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
    __db_details_specs = ('table_name', 'pk_field',  'last_appeal_data_field', 'days_valid_field', 'path_field',
                          'type_field')

    def __init__(self, conn, source_id, fetcher_procedure: Callable, update_interface: Callable, db_details: dict):
        self._update_interface = update_interface
        self._connection: sqlite3.Connection = conn
        self._db_cursor: sqlite3.Cursor = self._connection.cursor()

        assert source_id not in [inst.source_id for inst in getattr(self, f'_{self.__class__.__name__}__instances')], \
            'The updater on this source has been set already'

        assert set(self.get_db_specs()) & set(db_details.keys()) == set(self.get_db_specs()), \
            'One of the required database specification parameters is missing'

        self._db_details = db_details
        self.source_id = source_id

        assert self._db_cursor.execute(
            f'SELECT * FROM {db_details["table_name"]} WHERE {db_details["pk_field"]} = :source_id',
            (self.source_id,)
        ).fetchone(), f'No source in table with {source_id=}'

        self.fetch_data = fetcher_procedure

        getattr(self, f'_{self.__class__.__name__}__instances').append(self)

    def update_is_needed(self):
        details = self._db_details

        sql = '''
        SELECT {last_appeal_data_field}, {days_valid_field} 
        FROM {table_name} 
        WHERE {pk_field} = ?
        '''.format(**details)

        res = self._db_cursor.execute(sql, (self.source_id,)).fetchone()

        last_appeal, days_valid = datetime.date.fromisoformat(res[0]), datetime.timedelta(days=res[1])

        return True if last_appeal + days_valid <= datetime.date.today() else False

    def obtain_data(self):
        path = self.get_path_to_source()

        def preparer(rate: CurrencyRate):
            rate.info_source = self.source_id

        yield from (preparer(rate) for rate in self.fetch_data())

    def get_path_to_source(self):
        details = self._db_details

        sql = 'SELECT {path_field} FROM {table_name} WHERE {pk_field} = ?'.format(**details)
        res = self._db_cursor.execute(sql, (self.source_id,)).fetchone()
        return res[0]

    def update(self, on_nonexist_exc=None, *, commit_last_appeal_record=False):
        path = self.get_path_to_source()
        data = self.fetch_data(path)

        update_happened = False
        for rate in data:
            try:
                rate.info_source = self.source_id
                self._update_interface(rate)
                update_happened = True
            except:
                if on_nonexist_exc and isinstance(sys.exception(), on_nonexist_exc):
                    pass
                else:
                    raise

        if update_happened:
            datestamp = datetime.date.today()
            details = self._db_details.copy()
            details['datestamp'] = datestamp
            details['source_id'] = self.source_id
            sql = '''UPDATE {table_name} 
            SET {last_appeal_data_field} = :datestamp 
            WHERE {pk_field} = :source_id'''.format(**details)
            self._db_cursor.execute(sql, details)
            if commit_last_appeal_record:
                self._db_cursor.execute('COMMIT')

    @classmethod
    def get_db_specs(cls):
        return cls.__db_details_specs

