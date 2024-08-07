import sys
import urllib.error
from http import HTTPStatus
from http.client import HTTPException
from io import BytesIO
from typing import Callable
import logging.config
import web.apploggers as apploggers

import app.main
from web.data_objects import ExchangeRate, ConvertedExchangeRate
from web.wsgi_app_bases.wsgi_application_base import WSGIApplication, ResponseProcessingError
import app as coresrv
from app.data_objects import Currency, CurrencyRate
from web.updaters import get_er_updaters
from web.views import CurrencyExchangeAppViewLayer

ER_UPDATERS = get_er_updaters()

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

    def do_error_response(self, e):
        self._logger.error(msg='', exc_info=sys.exc_info())
        return super().do_error_response(e)

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

    def set_logging_level(self, level):
        self._logger.setLevel(level)

core_application = CurrencyExchangeRatesWSGIApp()


application = CurrencyExchangeAppViewLayer(underlying_app=core_application)


@core_application.at_route('/currencies')
class CurrenciesHandler(CurrencyExchangeRatesWSGIApp):

    def doGET(self):
        env, start_response = self.resp_ctxt.env, self.resp_ctxt.own_start_response
        self._logger.debug(f'Serving GET (current handler: for {self.resp_ctxt.env["SCRIPT_NAME"]})')
        start_response(HTTPStatus.OK, ())
        yield coresrv.get_all_currencies()

    def doPOST(self):
        env = self.resp_ctxt.env
        self._logger.debug(f'Serving POST (current handler: for {env["SCRIPT_NAME"]})')

        qd = self._parse_qsl(env, ('code', 'name', 'sign'))

        try:
            new_curr = Currency(None, qd['code'], qd['name'], qd['sign'])
        except ValueError as e:
            raise ResponseProcessingError(HTTPStatus.BAD_REQUEST, e.args[0])

        try:
            added_curr = coresrv.add_currency(new_curr)
        except coresrv.main.RequiredFieldAbsent as e:
            raise ResponseProcessingError(HTTPStatus.BAD_REQUEST, e.args[0])
        except coresrv.main.RecordOfSuchIdentityExists as e:
            raise ResponseProcessingError(HTTPStatus.CONFLICT, e.args[0])

        self.resp_ctxt.own_start_response(HTTPStatus.CREATED, ())

        yield added_curr


@core_application.at_route('/currency')
class CurrencyHandler(CurrencyExchangeRatesWSGIApp):

    def __call__(self, env, start_response):
        if not self._get_inner_handler(env['REQUEST_METHOD']):

            raise ResponseProcessingError(HTTPStatus.NOT_IMPLEMENTED)

        yield from super().__call__(env, start_response)

    def doGET(self):
        env, start_response = self.resp_ctxt.env, self.resp_ctxt.own_start_response
        self._logger.debug(f'Serving GET (current handler: for {env["SCRIPT_NAME"]})')
        path_comps = self._get_path_components(env)

        if len(path_comps) != 2:

            raise ResponseProcessingError(
                HTTPStatus.BAD_REQUEST,
                'Exactly one currency code should be provided as an endpoint of this resource'
            )

        curr_code = path_comps[1].upper()

        try:
            curr_query_obj = Currency(None, curr_code, None, None)
        except ValueError:

            raise ResponseProcessingError(
                HTTPStatus.BAD_REQUEST, 'Invalid currency code (valid is 3 alphabetical characters)'
            )

        curr_data_obj = coresrv.get_currency(curr_query_obj)

        if not curr_data_obj:

            raise ResponseProcessingError(HTTPStatus.NOT_FOUND, "Currency wasn't found")

        start_response(HTTPStatus.OK, ())

        yield curr_data_obj


@core_application.at_route('/exchangeRates')
class ExchangeRatesHandler(CurrencyExchangeRatesWSGIApp):

    def doGET(self):
        env, start_response = self.resp_ctxt.env, self.resp_ctxt.own_start_response
        self._logger.debug(f'Serving GET (current handler: for {env["SCRIPT_NAME"]})')
        try:
            rates = coresrv.get_all_exchange_rates()
        except app.main.sqlite3.Error as e:
            raise ResponseProcessingError(HTTPStatus.INTERNAL_SERVER_ERROR, e.args[0])

        er_list = []
        for rate in rates:
            bcurr = coresrv.get_currency(Currency(None, rate.base_currency_code, None, None))
            tcurr = coresrv.get_currency(Currency(None, rate.target_currency_code, None, None))

            er = ExchangeRate(rate.id, bcurr, tcurr, round(rate.rate, 2))

            er_list.append(er)

        start_response(HTTPStatus.OK, ())

        yield er_list

    def doPOST(self):
        env, start_response = self.resp_ctxt.env, self.resp_ctxt.own_start_response
        self._logger.debug(f'Serving POST (current handler: for {env["SCRIPT_NAME"]})')
        qd = self._parse_qsl(env, ('baseCurrencyCode', 'targetCurrencyCode', 'rate'))

        try:
            qd['rate'] = float(qd['rate'])
        except ValueError:
            raise ResponseProcessingError(HTTPStatus.BAD_REQUEST, 'Rate should be a numeric value')

        try:
            new_er = coresrv.add_exchange_rate(
                CurrencyRate(None, qd['baseCurrencyCode'], qd['targetCurrencyCode'], 1, qd['rate'], None)
            )
        except ValueError as e:
            raise ResponseProcessingError(HTTPStatus.BAD_REQUEST,  f'Bad currency code: {e.args[0]}')

        except app.main.RecordOfSuchIdentityExists as e:
            raise ResponseProcessingError(HTTPStatus.CONFLICT,  e.args[0])

        if not new_er:
            raise ResponseProcessingError(
                HTTPStatus.NOT_FOUND, 'One or more currencies is not present at applications database'
            )

        new_er = ExchangeRate(
            new_er.id,
            coresrv.get_currency(
                Currency(None, new_er.base_currency_code, None, None)
            ),
            coresrv.get_currency(
                Currency(None, new_er.target_currency_code, None, None)
            ),
            round(new_er.rate, 2)
        )

        start_response(HTTPStatus.CREATED, ())

        yield new_er


@core_application.at_route('/exchangeRate')
class ExchangeRateHandler(CurrencyExchangeRatesWSGIApp):

    def __call__(self, env, start_response):
        if not self._get_inner_handler(env['REQUEST_METHOD']):
            raise ResponseProcessingError(HTTPStatus.NOT_IMPLEMENTED)

        yield from super().__call__(env, start_response)

    def doGET(self):
        env, start_response = self.resp_ctxt.env, self.resp_ctxt.own_start_response
        self._logger.debug(f'Serving GET (current handler: for {env["SCRIPT_NAME"]})')

        query_rate = self._get_query_rate_from_url(env)

        rate = coresrv.get_exchange_rate(
            query_rate, strategy=app.main.FIND_RATE_BY_RECIPROCAL | app.main.FIND_RATE_BY_COMMON_TARGET
        )

        if not rate:
            raise ResponseProcessingError(
                HTTPStatus. NOT_IMPLEMENTED,
                f'Rate for {query_rate.base_currency_code} - {query_rate.target_currency_code} not found'
            )

        bcurr = coresrv.get_currency(Currency(None, rate.base_currency_code, None, None))
        tcurr = coresrv.get_currency(Currency(None, rate.target_currency_code, None, None))

        er = ExchangeRate(rate.id, bcurr, tcurr, round(rate.rate, 2))

        start_response(HTTPStatus.OK, ())
        yield er

    def doPATCH(self):
        env, start_response = self.resp_ctxt.env, self.resp_ctxt.own_start_response
        self._logger.debug(f'Serving PATCH (current handler: for {env["SCRIPT_NAME"]})')
        query_er = self._get_query_rate_from_url(env)

        qd = self._parse_qsl(env, ('rate',))

        try:
            qd['rate'] = float(qd['rate'])
        except ValueError:
            raise ResponseProcessingError(HTTPStatus.BAD_REQUEST, 'Rate should be a numeric value')

        query_er.rate = qd['rate']

        try:
            updated_er = coresrv.update_exchange_rate(query_er)
        except app.main.NoRecordToModify:
            raise ResponseProcessingError(
                HTTPStatus.NOT_FOUND,
                msg=f'Rate for {query_er.base_currency_code} - {query_er.target_currency_code} not found'
            )

        updated_er = ExchangeRate(
            updated_er.id,
            coresrv.get_currency(
                Currency(None, updated_er.base_currency_code, None, None)
            ),
            coresrv.get_currency(
                Currency(None, updated_er.target_currency_code, None, None)
            ),
            round(updated_er.rate, 2)
        )

        start_response(HTTPStatus.OK, ())

        yield updated_er

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


@core_application.at_route('/exchange')
class ExchangeHandler(CurrencyExchangeRatesWSGIApp):

    def doGET(self):
        env, start_response = self.resp_ctxt.env, self.resp_ctxt.own_start_response
        self._logger.debug(f'Serving GET (current handler: for {env["SCRIPT_NAME"]})')
        qd = self._parse_qsl(
            {
                'wsgi.input': BytesIO(env['QUERY_STRING'].encode()),
                'CONTENT_TYPE': 'application/x-www-form-urlencoded'
            },
            ('from', 'to', 'amount')
        )

        try:
            rate = coresrv.get_exchange_rate(
                CurrencyRate(None, qd['from'], qd['to'], None, None, None),
                strategy=app.main.FIND_RATE_BY_RECIPROCAL | app.main.FIND_RATE_BY_COMMON_TARGET
            )
        except ValueError as e:
            raise ResponseProcessingError(HTTPStatus.BAD_REQUEST, f'Invalid currency codes: {e.args[0]}')

        if not rate:
            raise ResponseProcessingError(HTTPStatus.NOT_FOUND, 'No such exchange_rate')

        bcurr = coresrv.get_currency(Currency(None, rate.base_currency_code, None, None))
        tcurr = coresrv.get_currency(Currency(None, rate.target_currency_code, None, None))

        try:
            amount = float(qd['amount'])
        except ValueError:
            raise ResponseProcessingError(HTTPStatus.BAD_REQUEST, 'Amount should be a numeric value')

        conv_amount = rate.reduced_rate * amount

        start_response(HTTPStatus.OK, ())

        yield ConvertedExchangeRate(bcurr, tcurr, round(rate.rate, 2), round(amount, 2), round(conv_amount, 2))
