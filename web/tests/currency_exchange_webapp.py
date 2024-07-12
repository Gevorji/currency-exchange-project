import unittest
import os
import sys
import json
import wsgiref
import wsgiref.util
from http import HTTPStatus
from io import BytesIO
from urllib.parse import quote, urlencode

import app as coreapp
import app.main
from app.data_objects import Currency, CurrencyRate
from web.tests.mock_wsgi_gateway import MockServerGateway
from web.wsgi_application import application, currency_as_dict, exch_rate_as_dict, http_status_enum_to_string

mock_env = {}

wsgiref.util.setup_testing_defaults(mock_env)

application.set_logging_level('DEBUG')

gw = MockServerGateway(mock_env)

coreapp.COMMIT_IF_SUCCESS = False


class BaseAppTest(unittest.TestCase):
    _gw = gw

    def setUp(self) -> None:
        self._gw.env = mock_env.copy()

    def tearDown(self) -> None:
        self._gw.clean_attrs()
        coreapp.connection.rollback()


class RootHandlerRespondsWithErrors(BaseAppTest):

    def test_RootRespondsWNotImplemented(self):
        inp = (('/currencies', 'PUT'), ('/', 'GET'), ('/', 'POST'), ('/exchange', 'POST'))
        for path_inf, meth in inp:
            with self.subTest(PATH_INFO=path_inf, METHOD=meth):
                self._gw.env['PATH_INFO'] = path_inf
                self._gw.env['REQUEST_METHOD'] = meth
                self._gw.run(application)
                self.assertEqual(self._gw.response_status, '501 Not Implemented')
            self._gw.clean_attrs()

    def test_RootRespondsWNotFound(self):
        self._gw.env['PATH_INFO'] = '/notSuppliedPath'
        self._gw.run(application)

        self.assertEqual(self._gw.response_status, '404 Not Found')

    def test_RootRespondsWBadRequest(self):
        inp = ('/curr-cies', 'currencies', 'cur rencies')

        for path_inf in inp:
            self._gw.env['PATH_INFO'] = path_inf
            self._gw.run(application)
            with self.subTest(PATH_INFO=path_inf):
                self.assertEqual(self._gw.response_status, '400 Bad Request')
            self._gw.clean_attrs()


class RootRespondsWSuccessStatuses(BaseAppTest):

    def test_RootRespondsWOkOnUnusualURIs(self):
        inp = ('///currencies', '/currency////RUB')

        for path_inf in inp:
            self._gw.env['PATH_INFO'] = path_inf
            self._gw.run(application)
            with self.subTest(PATH_INFO=path_inf):
                self.assertEqual(self._gw.response_status, '200 OK')
            self._gw.clean_attrs()


class CurrenciesEndPoint(BaseAppTest):

    def test_getCurrencies(self):
        env = mock_env.copy()
        env['SCRIPT_NAME'] = ''
        env['PATH_INFO'] = '/currencies'
        gw = MockServerGateway(env)

        gw.run(application)

        correct = json.dumps(list(currency_as_dict(cur) for cur in coreapp.get_all_currencies()))

        self.assertEqual(gw.result_data[0].decode(), correct)

    def test_postCurrenciesRequestSuccessful(self):
        gw = self._gw
        env = gw.env

        new_cur_qry = {'code': 'XXX', 'name': 'some_curr', 'sign': '$#'}

        qry_url_encoded = urlencode({quote(k): quote(v) for k, v in new_cur_qry.items()})

        env['PATH_INFO'] = '/currencies'
        env['REQUEST_METHOD'] = 'POST'
        env['wsgi.input'] = BytesIO(qry_url_encoded.encode())
        env['HTTP_CONTENT_TYPE'] = 'application/x-www-form-urlencoded'

        gw.run(application)

        resp_d = json.loads(gw.result_data[0].decode())
        new_id = coreapp.connection.execute('select max(currency_id) from currency').fetchone()[0]
        self.assertEqual(resp_d, {'id': new_id, 'code': 'XXX', 'name': 'some_curr', 'sign': '$#'})

    def test_respondsWConflictErrorOnAlreadyExistingCurrency(self):
        gw = self._gw
        env = gw.env

        new_cur_qry = {'code': 'AUD', 'name': 'Australian dollar', 'sign': '$#'}

        qry_url_encoded = urlencode({quote(k): quote(v) for k, v in new_cur_qry.items()})

        env['PATH_INFO'] = '/currencies'
        env['REQUEST_METHOD'] = 'POST'
        env['wsgi.input'] = BytesIO(qry_url_encoded.encode())
        env['HTTP_CONTENT_TYPE'] = 'application/x-www-form-urlencoded'

        gw.run(application)

        self.assertEqual(gw.response_status, http_status_enum_to_string(HTTPStatus.CONFLICT))


class CurrencyEndPoint(BaseAppTest):

    def test_getCurrencySuccessful(self):
        gw = self._gw
        env = gw.env

        env['PATH_INFO'] = '/currency/RUB'
        env['REQUEST_METHOD'] = 'GET'

        gw.run(application)
        correct = json.dumps(currency_as_dict(coreapp.get_currency(Currency(None, 'RUB', None, None))))

        self.assertEqual(
            correct,
            gw.result_data[0].decode()
        )

    def test_getCurrencyRespondsWErrorNotFound(self):
        gw = self._gw
        env = gw.env

        env['PATH_INFO'] = '/currency/XXX'
        env['REQUEST_METHOD'] = 'GET'

        gw.run(application)

        self.assertEqual(gw.response_status, http_status_enum_to_string(HTTPStatus.NOT_FOUND))


class ExchangeRatesEndPoint(BaseAppTest):

    def test_getExchangeRatesSuccessful(self):
        gw = self._gw
        env = gw.env

        env['PATH_INFO'] = '/exchangeRates'
        env['REQUEST_METHOD'] = 'GET'

        gw.run(application)

        correct = []
        for rate in coreapp.get_all_exchange_rates():
            bcurr = currency_as_dict(coreapp.get_currency(Currency(None, rate.base_currency_code, None, None)))
            tcurr = currency_as_dict(coreapp.get_currency(Currency(None, rate.target_currency_code, None, None)))

            drate = exch_rate_as_dict(rate)
            drate['baseCurrency'] = bcurr
            drate['targetCurrency'] = tcurr

            correct.append(drate)

        correct = json.dumps(correct)

        self.assertEqual(
            correct, gw.result_data[0].decode()
        )


class ExchangeRateEndPoint(BaseAppTest):

    def test_getExchangeRateSuccessful(self):
        gw = self._gw
        env = gw.env

        env['PATH_INFO'] = '/exchangeRate/USDRUB'
        env['REQUEST_METHOD'] = 'GET'

        correct = json.dumps(
            currency_as_dict(
                coreapp.get_exchange_rate(
                    CurrencyRate(None, 'USD', 'RUB', None, None, None), strategy=app.main.FIND_RATE_BY_RECIPROCAL
                )
            )
        )
        gw.run(application)
        self.assertEqual(correct, gw.result_data[0].decode())

    def test_getOrPostExchangeRateRespondsWBadRequest(self):
        gw = self._gw
        env = gw.env

        inp = ('/USDRUBXXX', '/USDRUB/XXX')

        for url in inp:
            for meth in ('GET', 'POST'):
                with self.subTest(PATH_PART=url, METHOD=meth):
                    env['REQUEST_METHOD'] = meth
                    env['PATH_INFO'] = f'/exchangeRate{url}'
                    gw.run(application)
                    self.assertEqual(gw.response_status, http_status_enum_to_string(HTTPStatus.BAD_REQUEST))
                    gw.clean_attrs()

    def test_patchExchangeRateSuccessful(self):
        gw = self._gw
        env = gw.env

        qry_d = {'rate': 100}
        env['PATH_INFO'] = '/exchangeRate/USDRUB'
        env['REQUEST_METHOD'] = 'PATCH'
        env['wsgi.input'] = BytesIO(urlencode(qry_d).encode())

        gw.run(application)

        correct = json.dumps(currency_as_dict(app.get_exchange_rate(CurrencyRate(None, 'USD', 'RUB', None, None, None))))

        self.assertEqual(
            correct, gw.result_data[0].decode()
        )

    def test_patchExchangeRateRespondsWNotFound(self):
        gw = self._gw
        env = gw.env

        qry_d = {'rate': 100}
        env['PATH_INFO'] = '/exchangeRate/XXXBBB'
        env['REQUEST_METHOD'] = 'PATCH'
        env['wsgi.input'] = BytesIO(urlencode(qry_d).encode())

        gw.run(application)

        self.assertEqual(gw.response_status, http_status_enum_to_string(HTTPStatus.NOT_FOUND))


