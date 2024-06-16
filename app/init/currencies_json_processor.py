import json


def get_currencies_from_json(json_obj):
    currencies_json = json.load(open(json_obj, 'rb'))

    for currency_code in currencies_json:
        record = (currency_code, currencies_json[currency_code]['name'],
                  currencies_json[currency_code]['symbol']['grapheme'])

        yield record
