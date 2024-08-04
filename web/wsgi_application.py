import dataclasses
import json
import sys
import urllib.error
from collections import OrderedDict
from http import HTTPStatus
from http.client import HTTPException
from io import BytesIO
from typing import Callable, Iterable
import logging
import logging.config
import web.apploggers as apploggers

import app.main
from web.wsgi_application_base import WSGIApplication, http_status_enum_to_string, ResponseProcessingError
import app as coresrv
from app.data_objects import Currency, CurrencyRate
from app.main import substitute_keys
from web.updaters import get_er_updaters

EXCHANGE_RATE_FIELDS_MAPPING = {
    'base_currency_id': 'baseCurrency',
    'target_currency_id': 'targetCurrency'
}

CURRENCY_FIELDS_MAPPING = {
    'full_name': 'name'
}

ER_UPDATERS = get_er_updaters()


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
    d = dataclass_as_specified_dict(er, ('id', 'base_currency_code', 'target_currency_code', 'rate'))
    substitute_keys(d, EXCHANGE_RATE_FIELDS_MAPPING)
    return d


logging.config.dictConfig(apploggers.logconfig)


class CurrencyExchangeRatesWSGIApp(WSGIApplication):
    _logger = logging.getLogger(apploggers.APP_LOGGER_NAME)

    def __call__(self, env, start_response):
        self._logger.debug(
            '=Request arrived at {}=\nEnvironment:{}'
            .format(env['SCRIPT_NAME'], '\n\t'.join(str(itm) for itm in env.items()))
        )
        self._logger.info(
            f'Starting response (current handler: for {env["SCRIPT_NAME"]}). Request at {env["PATH_INFO"]}'
        )

        if env['REQUEST_METHOD'] == 'GET' and env['SCRIPT_NAME'].casefold() == '/exchangeRates'.casefold():
            try:
                self.refresh_data()
            except urllib.error.URLError:
                pass

        res = super().__call__(env, start_response)

        self._logger.info(f'Finished response (current handler: for {env["SCRIPT_NAME"]})')

        return res

    def _delegate_wsgi_call(self, env: dict, start_response: Callable):
        self._logger.debug(f'Delegating call to {env["PATH_INFO"]}')

        return super()._delegate_wsgi_call(env, start_response)

    def call_with_exception_catch(self, func, env: dict, start_response: Callable):
        try:
            response: Iterable = func(env, start_response)
        except Exception:
            self._logger.error(msg='', exc_info=sys.exc_info())
            start_response(http_status_enum_to_string(HTTPStatus.INTERNAL_SERVER_ERROR), [], sys.exc_info())
        else:
            return response

    def refresh_data(self):
        for updr in ER_UPDATERS:
            try:
                do_update = updr.update_is_needed()
            except TypeError:
                do_update = True
            if do_update:
                try:
                    updr.update(app.main.NoRecordToModify, commit_last_appeal_record=True)
                except HTTPException as e:
                    self._logger.info(
                        f'Update is needed ({updr.source_id}), but were not able to accomplish it due to problem: {e}'
                    )
                self._logger.info('Rates were updated successfully')
            else:
                self._logger.debug('Update not needed')

    def do_json_error_response(self, code: HTTPStatus, headers: list, start_response, msg=None):
        self._logger.error(str(sys.exc_info()[2]))
        return super().do_json_error_response(code, headers, start_response, msg)

    def set_logging_level(self, level):
        self._logger.setLevel(level)


application = CurrencyExchangeRatesWSGIApp()


@application.at_route('/currencies')
class CurrenciesHandler(CurrencyExchangeRatesWSGIApp):

    def doGET(self, env, start_response):
        self._logger.debug(f'Serving GET (current handler: for {env["SCRIPT_NAME"]})')
        query_res = [currency_as_dict(curr) for curr in coresrv.get_all_currencies()]
        json_data = json_dumpb(query_res)

        headers = [('Content-Type', 'application/json')]
        start_response(
            http_status_enum_to_string(HTTPStatus.OK),
            headers
        )

        yield json_data

    def doPOST(self, env, start_response):
        self._logger.debug(f'Serving POST (current handler: for {env["SCRIPT_NAME"]})')
        try:
            qd = self._parse_qsl(env, ('code', 'name', 'sign'))
        except ResponseProcessingError as e:
            yield from self.do_json_error_response(e.args[0], [], start_response, e.args[1])
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


@application.at_route('/currency')
class CurrencyHandler(CurrencyExchangeRatesWSGIApp):

    def __call__(self, env, start_response):
        if not self._get_inner_handler(env['REQUEST_METHOD']):
            yield from self.do_json_error_response(HTTPStatus.NOT_IMPLEMENTED, [], start_response)
            return

        yield from super().__call__(env, start_response)

    def doGET(self, env, start_response):
        self._logger.debug(f'Serving GET (current handler: for {env["SCRIPT_NAME"]})')
        path_comps = self._get_path_components(env)

        if len(path_comps) != 2:
            yield from self.do_json_error_response(
                HTTPStatus.BAD_REQUEST, [], start_response,
                'Exactly one currency code should be provided as an endpoint of this resource'
            )
            return

        curr_code = path_comps[1].upper()

        try:
            curr_query_obj = Currency(None, curr_code, None, None)
        except ValueError:
            yield from self.do_json_error_response(
                HTTPStatus.BAD_REQUEST, [], start_response,
                'Invalid currency code (valid is 3 alphabetical characters)'
            )
            return

        curr_data_obj = coresrv.get_currency(curr_query_obj)

        if not curr_data_obj:
            yield from self.do_json_error_response(
                HTTPStatus.NOT_FOUND, [], start_response, "Currency wasn't found"
            )
            return

        json_data = json_dumpb(currency_as_dict(curr_data_obj))

        headers = [('Content-Type', 'application/json')]
        start_response((http_status_enum_to_string(HTTPStatus.OK)), headers)

        yield json_data


@application.at_route('/exchangeRates')
class ExchangeRatesHandler(CurrencyExchangeRatesWSGIApp):

    def doGET(self, env, start_response):
        self._logger.debug(f'Serving GET (current handler: for {env["SCRIPT_NAME"]})')
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

            drate = {'id': rate.id, 'baseCurrency': bcurr, 'targetCurrency': tcurr, 'rate': round(rate.rate, 2)}

            er_list.append(drate)

        json_data = json_dumpb(er_list)

        start_response(
            http_status_enum_to_string(HTTPStatus.OK), [('Content-Type', 'application/json')]
        )

        yield json_data

    def doPOST(self, env, start_response):
        self._logger.debug(f'Serving POST (current handler: for {env["SCRIPT_NAME"]})')
        try:
            qd = self._parse_qsl(env, ('baseCurrencyCode', 'targetCurrencyCode', 'rate'))
        except ResponseProcessingError as e:
            yield from self.do_json_error_response(e.args[0], [], start_response, e.args[1])
            return

        try:
            qd['rate'] = float(qd['rate'])
        except ValueError:
            yield from self.do_json_error_response(
                HTTPStatus.BAD_REQUEST, [], start_response, 'Rate should be a numeric value'
            )

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

        if not new_er:
            yield from self.do_json_error_response(
                HTTPStatus.NOT_FOUND, [], start_response,
                'One or more currencies is not present at applications database'
            )
            return

        start_response(
            http_status_enum_to_string(HTTPStatus.CREATED), [('Content-Type', 'application/json')]
        )

        yield json_dumpb(exch_rate_as_dict(new_er))


@application.at_route('/exchangeRate')
class ExchangeRateHandler(CurrencyExchangeRatesWSGIApp):

    def __call__(self, env, start_response):
        if not self._get_inner_handler(env['REQUEST_METHOD']):
            yield from self.do_json_error_response(HTTPStatus.NOT_IMPLEMENTED, [], start_response)
            return

        yield from super().__call__(env, start_response)

    def doGET(self, env, start_response):
        self._logger.debug(f'Serving GET (current handler: for {env["SCRIPT_NAME"]})')
        try:
            query_rate = self._get_query_rate_from_url(env)
        except ResponseProcessingError as e:
            yield from self.do_json_error_response(e.args[0], [], start_response, e.args[1])
            return

        rate = coresrv.get_exchange_rate(
            query_rate, strategy=app.main.FIND_RATE_BY_RECIPROCAL | app.main.FIND_RATE_BY_COMMON_TARGET
        )

        if not rate:
            yield from self.do_json_error_response(
                HTTPStatus.NOT_FOUND, [], start_response,
                f'Rate for {query_rate.base_currency_code} - {query_rate.target_currency_code} not found'
            )
            return

        start_response(
            http_status_enum_to_string(HTTPStatus.OK), [('Content-Type', 'application/json')]
        )

        bcurr = currency_as_dict(coresrv.get_currency(Currency(None, rate.base_currency_code, None, None)))
        tcurr = currency_as_dict(coresrv.get_currency(Currency(None, rate.target_currency_code, None, None)))

        drate = {'id': rate.id, 'baseCurrency': bcurr, 'targetCurrency': tcurr, 'rate': round(rate.rate, 2)}

        json_data = json_dumpb(drate)
        yield json_data

    def doPATCH(self, env, start_response):
        self._logger.debug(f'Serving PATCH (current handler: for {env["SCRIPT_NAME"]})')
        try:
            query_er = self._get_query_rate_from_url(env)
        except ResponseProcessingError as e:
            yield from self.do_json_error_response(e.args[0], [], start_response, e.args[1])
            return

        try:
            qd = self._parse_qsl(env, ('rate',))
        except ResponseProcessingError as e:
            yield from self.do_json_error_response(e.args[0], [], start_response, e.args[1])
            return

        try:
            qd['rate'] = float(qd['rate'])
        except ValueError:
            yield from self.do_json_error_response(
                HTTPStatus.BAD_REQUEST, [], start_response, 'Rate should be a numeric value'
            )

        query_er.rate = qd['rate']

        try:
            updated_er = coresrv.update_exchange_rate(query_er)
        except app.main.NoRecordToModify:
            msg = f'Rate for {query_er.base_currency_code} - {query_er.target_currency_code} not found'
            yield from self.do_json_error_response(
                HTTPStatus.NOT_FOUND, [], start_response, msg
            )
            return

        start_response(
            http_status_enum_to_string(HTTPStatus.OK), [('Content-Type', 'application/json')]
        )

        yield json_dumpb(exch_rate_as_dict(updated_er))

    def _get_query_rate_from_url(self, env):
        path_comps = self._get_path_components(env)

        if len(path_comps) != 2 or len(path_comps[1]) != 6:
            msg = 'Exactly 1 currency pair in form XXXXXX should be provided as an endpoint for this resource'
            raise ResponseProcessingError(HTTPStatus.BAD_REQUEST, msg)

        bcode, tcode = path_comps[1][:3].upper(), path_comps[1][3:].upper()

        try:
            query_rate = CurrencyRate(None, bcode, tcode, None, None, None)
        except ValueError as e:
            raise ResponseProcessingError(HTTPStatus.BAD_REQUEST, e.args[0])

        return query_rate


@application.at_route('/exchange')
class ExchangeHandler(CurrencyExchangeRatesWSGIApp):

    def doGET(self, env, start_response):
        self._logger.debug(f'Serving GET (current handler: for {env["SCRIPT_NAME"]})')
        try:
            qd = self._parse_qsl(
                {
                    'wsgi.input': BytesIO(env['QUERY_STRING'].encode()),
                    'CONTENT_TYPE': 'application/x-www-form-urlencoded'
                },
                ('from', 'to', 'amount')
            )
        except ResponseProcessingError as e:
            yield from self.do_json_error_response(
                HTTPStatus.BAD_REQUEST, [], start_response, e.args[1]
            )
            return

        try:
            rate = coresrv.get_exchange_rate(
                CurrencyRate(None, qd['from'], qd['to'], None, None, None),
                strategy=app.main.FIND_RATE_BY_RECIPROCAL | app.main.FIND_RATE_BY_COMMON_TARGET
            )
        except ValueError as e:
            yield from self.do_json_error_response(
                HTTPStatus.BAD_REQUEST,
                [], start_response,
                f'Invalid currency codes: {e.args[0]}')
            return

        if not rate:
            yield from self.do_json_error_response(
                HTTPStatus.NOT_FOUND, [], start_response, 'No such exchange_rate'
            )
            return

        bcurr = coresrv.get_currency(Currency(None, rate.base_currency_code, None, None))
        tcurr = coresrv.get_currency(Currency(None, rate.target_currency_code, None, None))

        try:
            amount = float(qd['amount'])
        except ValueError:
            yield from self.do_json_error_response(
                HTTPStatus.BAD_REQUEST, [], start_response, 'Amount should be a numeric value'
            )
            return

        conv_amount = rate.reduced_rate * amount

        response = {
            'baseCurrency': currency_as_dict(bcurr),
            'targetCurrency': currency_as_dict(tcurr),
            'rate': round(rate.rate, 2),
            'amount': round(amount, 2),
            'convertedAmount': round(conv_amount, 2)
        }

        start_response(
            http_status_enum_to_string(HTTPStatus.OK), [('Content-Type', 'application/json')]
        )

        yield json_dumpb(response)
