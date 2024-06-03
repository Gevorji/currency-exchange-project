import sqlite3
import datetime

def set_connection(conn):

    connection = conn


class CurrencyRatesUpdater:
    """
    Provides functionality for keeping currency rates up-to-date in application's database
    """
    __db_details_specs = ('table_name', 'last_appeal_data_field')

    def __init__(self, conn, db_details: dict):
        self.__connection: sqlite3.Connection = conn
        self.__db_cursor: sqlite3.Cursor = self.__connection.cursor()

        assert set(self.__db_details_specs) & set(db_details.keys()) == set(self.__db_details_specs), \
            'One of the required database specification parameters is missing'

        self.__db_details = db_details

    def update_is_needed(self, source_id):
        details = self.__db_details
        self.__db_cursor.execute('SELECT :last_appeal_data_field from :table_name', details)
