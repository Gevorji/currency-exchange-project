import sqlite3
import datetime

def set_connection(conn):

    connection = conn


class CurrencyRatesUpdater:
    """
    Provides functionality for keeping currency rates up-to-date in application's database
    """

    def __init__(self, conn, history_of_updates_table_name):
        self.__connection: sqlite3.Connection = conn
        self.__db_cursor: sqlite3.Cursor = self.__connection.cursor()
        self.__name_of_updates_table = history_of_updates_table_name

    def update_is_needed(self):
        self.__db_cursor.execute('SELECT last_appeal from ', (self.__name_of_updates_table,))
