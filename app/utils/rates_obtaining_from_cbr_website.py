from urllib.request import urlopen

from app.utils.html_table_parser import HtmlTableDataExtractor
from app.utils.rate_calculations import complete_building_set_of_rates
from app.data_objects import CurrencyRate


COMMON_TARGET_CURRENCY_CODE = 'RUB'
RATE_PRECISION = 4


def obtain_rates(url: str, prepare_func=None):

    html = urlopen(url).read().decode('utf-8')

    data = (prepare_func(rate) for rate in process_data_from_html_table(html)) \
        if prepare_func else process_data_from_html_table(html)

    yield from data


def prepare_for_insertion_into_db(data_obj: CurrencyRate):
    """
    Transforms data obj into a row valid for insertion into DB.
    """
    return (data_obj.base_currency_code, data_obj.target_currency_code,
            round(data_obj.rate, RATE_PRECISION))


def process_data_from_html_table(html):

    parser = HtmlTableDataExtractor()

    data = parser.feed(html)
    rates = []

    for table in data:
        for record in table[1:]:  # TODO: do headers row recognition
            data_obj = make_data_object(record)
            rates.append(data_obj)

    yield from complete_building_set_of_rates(rates)


def make_data_object(data: tuple):
    # Responsible for constructing valid data object depending on record structure
    __, base_currency_code, units, _, rate = data

    # string preparations
    rate = rate.replace(',', '.')

    return CurrencyRate(None, base_currency_code, COMMON_TARGET_CURRENCY_CODE, int(units), float(rate), None)


if __name__ == '__main__':
    rates = list(obtain_rates(SOURCE_URL))
    for rate in rates:
        print(rate[0], rate[1])
    print(len(rates))
