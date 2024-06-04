import sqlite3
import datetime
from abc import ABC, abstractmethod


def adapt_date_iso(val):
    return val.isoformat()


sqlite3.register_adapter(datetime.date, adapt_date_iso)


class CurrencyRatesUpdater(ABC):
    """
    Provides functionality for keeping currency rates up-to-date in application's database
    """
    __db_details_specs = ('table_name', '', 'pk_field',  'last_appeal_data_field', 'days_valid_field', 'path_field',
                          'type_field')

    def __init__(self, conn, source_id, db_details: dict):
        self.__connection: sqlite3.Connection = conn
        self.__db_cursor: sqlite3.Cursor = self.__connection.cursor()

        assert set(self.__db_details_specs) & set(db_details.keys()) == set(self.__db_details_specs), \
            'One of the required database specification parameters is missing'

        db_details['source_id'] = source_id
        assert self.__db_cursor.execute('SELECT * FROM :table_name WHERE :pk_field = :source_id').fetchone(), \
            f'No source in table with {source_id=}'
        self.__db_details = db_details

    def update_is_needed(self):
        details = self.__db_details
        res = self.__db_cursor.execute(
            'SELECT :last_appeal_data_field, :days_valid_field FROM :table_name WHERE :pk_field = :source_id', details
        ).fetchone()

        last_appeal, days_valid = datetime.date.fromisoformat(res[0]), datetime.timedelta(days=res[1])

        return True if last_appeal + days_valid <= datetime.date.today() else False

    @abstractmethod
    def update(self, source_id):
        pass

    @abstractmethod
    def obtain_data(self):
        pass

    @abstractmethod
    def fill_table_with_data(self):
        pass

    def get_path_to_source(self):
        details = self.__db_details

        res = self.__db_cursor.execute('SELECT :path_field FROM :table_name WHERE :pk_field = :source_id',
                                       details).fetchone()
        return res[0]