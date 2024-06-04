from rates_obtaining_from_cbr_website import obtain_rates
from CurrencyRatesUpdaterABC import CurrencyRatesUpdater


class CbrRatesUpdater(CurrencyRatesUpdater):

    def obtain_data(self):
        path = self.get_path_to_source()
        return obtain_rates(path)

    def update(self, source_id):
        rates = self.obtain_data()

        self.__db_cursor.executemany(
            '''UPDATE exchange_rates SET rate = :rate 
            WHERE base_currency_id
            '''
            )
