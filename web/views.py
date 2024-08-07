import dataclasses
import json
from collections import OrderedDict
from http import HTTPStatus
from typing import Iterable

from app.data_objects import Currency, CurrencyRate
from app.main import substitute_keys
from web.viewstools import View, ViewHolder
from web.data_objects import ExchangeRate, ConvertedExchangeRate
from web.wsgi_app_bases.wsgi_middleware_base import WSGIMiddleware

EXCHANGE_RATE_FIELDS_MAPPING = {
    'base_currency_id': 'baseCurrency',
    'target_currency_id': 'targetCurrency'
}

CURRENCY_FIELDS_MAPPING = {
    'full_name': 'name'
}


def http_status_enum_to_string(status: HTTPStatus):
    return f'{status.value} {status.phrase}'


def dataclass_as_specified_dict(dataclass: dataclasses.dataclass, fields: tuple):
    d = OrderedDict()
    for f in fields:
        d[f] = getattr(dataclass, f)
    return d


def exchange_rate_as_specified_dict(er: ExchangeRate):
    return dataclass_as_specified_dict(er, ('id', 'baseCurrency', 'targetCurrency', 'rate'))


def currency_as_dict(currency: Currency):
    d = dataclass_as_specified_dict(currency, ('id', 'full_name', 'code', 'sign'))
    substitute_keys(d, CURRENCY_FIELDS_MAPPING)
    return d


def json_currency(currency: Currency):
    d = currency_as_dict(currency)
    return json.dumps(d)


def json_currencies(currencies: Iterable[Currency]):
    return json.dumps([currency_as_dict(c) for c in currencies])


def json_exchange_rate(er: ExchangeRate):
    d = dataclass_as_specified_dict(er, ('id', 'baseCurrency', 'targetCurrency', 'rate'))
    d['baseCurrency'] = currency_as_dict(d['baseCurrency'])
    d['targetCurrency'] = currency_as_dict(d['targetCurrency'])
    return json.dumps(d)


def json_exchange_rates(ers: Iterable[ExchangeRate]):
    return json.dumps([json.loads(json_exchange_rate(c)) for c in ers])


def json_converted_rate(converted_er: ConvertedExchangeRate):
    d = dataclass_as_specified_dict(
        converted_er, ('baseCurrency', 'targetCurrency', 'rate', 'amount', 'convertedAmount')
    )
    d['baseCurrency'] = json_currency(d['baseCurrency'])
    d['targetCurrency'] = json_currency(d['targetCurrency'])

    return json.dumps(d)


def json_message(msg: str):
    return json.dumps({'message': msg})


view_holder = ViewHolder()


view_holder.add_view('/currency', View(json_currency, 'application/json'))
view_holder.add_view('/currencies', View(json_currencies, 'application/json'))
view_holder.add_view('/exchangeRate', View(json_exchange_rate, 'application/json'))
view_holder.add_view('/exchangeRates', View(json_exchange_rates, 'application/json'))
view_holder.add_view('/exchange', View(json_converted_rate, 'application/json'))
view_holder.add_view('message', View(json_message, 'application/json'))


class CurrencyExchangeAppViewLayer(WSGIMiddleware):

    def __init__(self, underlying_app):
        super().__init__(underlying_app)
        self.views = view_holder

    def modify_headers(self, env, headers):
        headers.insert(1, ('Content-type', 'application/json'))

    def modify_error_response_headers(self, e, headers):
        headers.insert(1, ('Content-type', 'application/json'))

    def process_data(self, data):
        rc = self.resp_ctxt
        method = rc.env['REQUEST_METHOD']
        fmt = 'application/json'
        endpoint = '/' + self._get_path_components(rc.env)[1]
        view = self.views.get_view(endpoint, fmt)

        if type(data) is str:
            view = self.views.get_view('message', fmt)
            return view.apply(data).encode()

        if method == 'POST':
            if endpoint.casefold() == '/currencies'.casefold():
                view = self.views.get_view('/currency', fmt)
            if endpoint.casefold() == '/exchangeRates'.casefold():
                view = self.views.get_view('/exchangeRate', fmt)

        if not data:
            return b''

        return view.apply(data).encode()

    def process_status(self, status):
        return http_status_enum_to_string(status)

    def __getattribute__(self, item):
        try:
            return super().__getattribute__(item)
        except AttributeError:
            return self.underlying_layer.__getattribute__(item)

