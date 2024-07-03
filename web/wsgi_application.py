import dataclasses
import http.client
import json
from functools import partial
from collections import OrderedDict
from http import HTTPStatus
from urllib.parse import parse_qsl

import app.main
from .wsgi_application_base import WSGIApplication, http_status_enum_to_string
import app as coresrv
from app.data_objects import Currency, CurrencyRate
from app.main import substitute_keys

application = WSGIApplication()

EXCHANGE_RATE_FIELDS_MAPPING = {
    'base_currency_id': 'baseCurrency',
    'target_currency_id': 'targetCurrency'
}

CURRENCY_FIELDS_MAPPING = {
    'full_name': 'name'
}

def dataclass_as_specified_dict(dataclass: dataclasses.dataclass, fields: tuple):
    d = OrderedDict()
    for f in fields:
        d[f] = getattr(dataclass, f)
    return d


def json_dumpb(obj, *args, encoding='utf-8', **kwargs):
    return json.dumps(obj, *args, **kwargs).encode(encoding)


def currency_as_dict(curr: Currency):
    d = dataclass_as_specified_dict(curr, ('id', 'full_name', 'code', 'sign'))
    substitute_keys(d, CURRENCY_FIELDS_MAPPING)
    return d


def exch_rate_as_dict(er: CurrencyRate):
    d = dataclass_as_specified_dict(er, ('id', 'base_currency_id', 'target_currency_id', 'rate'))
    substitute_keys(d, EXCHANGE_RATE_FIELDS_MAPPING)
    return d


@application.at_route('/currencies')
class CurrenciesHandler(WSGIApplication):

    def doGET(self, env, start_response):
        query_res = [currency_as_dict(curr) for curr in coresrv.get_all_currencies()]
        json_data = json_dumpb(query_res)

        headers = [('Content-Type', 'application/json')]
        start_response(
            http_status_enum_to_string(HTTPStatus.OK),
            headers
        )

        yield json_data

    def doPOST(self, env, start_response):
        if env.get('HTTP_CONTENT_TYPE') != 'application/x-www-form-urlencoded':
            yield from self.do_json_error_response(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE, [], start_response,
                'Required x-www-form-urlencoded'
            )
            return

        try:
            qd = dict(parse_qsl(env['wsgi.input'].read().decode(), strict_parsing=True))

            if not {'name', 'code', 'sign'} - set(qd.keys()) == set():
                raise AssertionError()
        except (ValueError, AssertionError):
            yield from self.do_json_error_response(
                HTTPStatus.BAD_REQUEST, [], start_response, 'Bad x-www-form-urlencoded'
            )
            return
        except UnicodeDecodeError:
            yield from self.do_json_error_response(
                HTTPStatus.UNPROCESSABLE_ENTITY, [], start_response, 'Was not able to decode body'
            )
            return

        try:
            new_curr = Currency(None, qd['code'], qd['name'], qd['sign'])
        except ValueError as e:
            yield from self.do_json_error_response(
                HTTPStatus.BAD_REQUEST, [], start_response, e.args[0]
            )
            return

        try:
            added_curr = coresrv.add_currency(new_curr)
        except coresrv.main.RequiredFieldAbsent as e:
            yield from self.do_json_error_response(
                HTTPStatus.BAD_REQUEST, [], start_response, e.args[0]
            )
            return
        except coresrv.main.RecordOfSuchIdentityExists as e:
            yield from self.do_json_error_response(
                HTTPStatus.CONFLICT, [], start_response, e.args[0]
            )
            return
        except Exception as e:
            yield from self.do_json_error_response(
                HTTPStatus.INTERNAL_SERVER_ERROR, [], start_response, e.args[0]
            )
            return

        start_response(
            http_status_enum_to_string(HTTPStatus.CREATED), (('Content-Type', 'application/json'),)
        )

        yield json_dumpb(currency_as_dict(added_curr))


class CurrencyHandler(WSGIApplication):

    def doGET(self, env, start_response):
        path_comps = self._get_path_components(env)
        curr_code = path_comps[0].upper()

        if len(path_comps) != 2:
            headers = []
            json_msg = json_dumpb(
                {'message': 'Exactly one currency code should be provided as an endpoint of this resource'}
            )
            headers.append(('Content-Type', 'text/json'))

            yield from self.do_json_error_response(HTTPStatus.BAD_REQUEST, headers, start_response, json_msg)
            return

        try:
            curr_query_obj = Currency(None, curr_code, None, None)
        except ValueError:
            headers = []
            json_msg = json_dumpb(
                {'message': 'Invalid currency code (valid is 3 alphabetical characters)'}
            )
            headers.append(('Content-Type', 'text/json'))

            yield from self.do_json_error_response(
                HTTPStatus.BAD_REQUEST, (('Content-Type', 'text/json'),), start_response, json_msg
            )
            return

        curr_data_obj = coresrv.get_currency(curr_query_obj)

        if not curr_data_obj:
            headers = []
            json_msg = json_dumpb(
                {'message': "Currency wasn't found"}
            )
            headers.append(('Content-Type', 'text/json'))

            yield from self.do_json_error_response(HTTPStatus.NOT_FOUND, headers, start_response, json_msg)
            return

        json_data = json_dumpb(currency_as_dict(curr_data_obj))

        headers = [('Content-Type', 'application/json')]
        start_response(HTTPStatus.OK, headers)

        yield json_data


@application.at_route('/exchangeRates')
class ExchangeRatesHandler(WSGIApplication):

    def doGET(self, env, start_response):
        try:
            rates = coresrv.get_all_exchange_rates()
        except app.main.sqlite3.Error as e:
                yield from self.do_json_error_response(
                    HTTPStatus.INTERNAL_SERVER_ERROR, [], start_response, e.args[0]
                )
                return

        er_list = []
        for rate in rates:
            bcurr = currency_as_dict(coresrv.get_currency(Currency(None, rate.base_currency_code, None, None)))
            tcurr = currency_as_dict(coresrv.get_currency(Currency(None, rate.target_currency_code, None, None)))

            drate = exch_rate_as_dict(rate)
            drate['baseCurrency'] = bcurr
            drate['targetCurrency'] = tcurr

            er_list.append(rate)

        json_data = json_dumpb(er_list)

        start_response(
            http_status_enum_to_string(HTTPStatus.OK), (('Content-Type', 'application/json'),)
        )

        yield json_data

    def doPOST(self, env, start_response):
        if env.get('HTTP_CONTENT_TYPE') != 'application/x-www-form-urlencoded':
            yield from self.do_json_error_response(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE, [], start_response,
                'Required x-www-form-urlencoded'
            )
            return

        try:
            qd = dict(parse_qsl(env['wsgi.input'].read().decode(), strict_parsing=True))

            if not {'baseCurrencyCode', 'targetCurrencyCode', 'rate'} - set(qd.keys()) == set():
                raise AssertionError()
        except (ValueError, AssertionError):
            yield from self.do_json_error_response(
                HTTPStatus.BAD_REQUEST, [], start_response, 'Bad x-www-form-urlencoded'
            )
            return
        except UnicodeDecodeError:
            yield from self.do_json_error_response(
                HTTPStatus.UNPROCESSABLE_ENTITY, [], start_response, 'Was not able to decode body'
            )
            return

        try:
            new_er = coresrv.add_exchange_rate(
                CurrencyRate(None, qd['baseCurrencyCode'], qd['targetCurrencyCode'], 1, qd['rate'], None)
            )
        except ValueError as e:
            yield from self.do_json_error_response(
                HTTPStatus.BAD_REQUEST, [], start_response, f'Bad currency code: {e.args[0]}'
            )
            return
        except app.main.RecordOfSuchIdentityExists as e:
            yield from self.do_json_error_response(
                HTTPStatus.CONFLICT, [], start_response, e.args[0]
            )
            return
        except app.main.QueryError:
            msg = 'One or more currencies is not present at applications database'
            yield from self.do_json_error_response(
                HTTPStatus.NOT_FOUND, [], start_response, msg
            )
            return

        start_response(
            http_status_enum_to_string(HTTPStatus.CREATED), (('Content-Type', 'application/json'),)
        )

        yield json_dumpb(exch_rate_as_dict(new_er))


@application.at_route('/exchangeRate')
class ExchangeRateHandler(WSGIApplication):

    def doGET(self, env, start_response):
        path_comps = self._get_path_components(env)

        if len(path_comps) != 2 or len(path_comps[1]) != 6:
            msg = 'Exactly 1 currency pair in for XXXXXX should be provided as an endpoint for this resource'
            yield from self.do_json_error_response(
                HTTPStatus.BAD_REQUEST, [], start_response, msg
            )
            return

        bcode, tcode = path_comps[1][:3].upper(), path_comps[1][3:].upper()

        try:
            query_rate = CurrencyRate(None, bcode, tcode, None, None, None)
        except ValueError as e:
            yield from self.do_json_error_response(
                HTTPStatus.BAD_REQUEST, [], start_response, e.args[0]
            )
            return

        rate = coresrv.get_exchange_rate(
            query_rate, strategy=app.main.FIND_RATE_BY_RECIPROCAL | app.main.FIND_RATE_BY_COMMON_TARGET
        )

        if rate:
            start_response(
                HTTPStatus.OK, (('Content-Type', 'application/json'),)
            )

            bcurr = currency_as_dict(coresrv.get_currency(Currency(None, rate.base_currency_code, None, None)))
            tcurr = currency_as_dict(coresrv.get_currency(Currency(None, rate.target_currency_code, None, None)))

            drate = exch_rate_as_dict(rate)
            drate['baseCurrency'] = bcurr
            drate['targetCurrency'] = tcurr

            json_data = json_dumpb(drate)
            yield json_data




