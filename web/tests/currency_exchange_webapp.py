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
from app.data_objects import Currency, CurrencyRate
from web.data_objects import ExchangeRate
from web.tests.mock_wsgi_gateway import MockServerGateway
from web.wsgi_application import application
from web.views import (
    json_currency, json_currencies, json_exchange_rate,
    json_exchange_rates, json_converted_rate, http_status_enum_to_string
)

mock_env = {}

wsgiref.util.setup_testing_defaults(mock_env)

application.set_logging_level('DEBUG')

gw = MockServerGateway(mock_env)

coreapp.connect_db('test.db')

coreapp.COMMIT_IF_SUCCESS = False


class BaseAppTest(unittest.TestCase):
    _gw = gw

    def setUp(self) -> None:
        self._gw.env = mock_env.copy()

    def tearDown(self) -> None:
        self._gw.clean_attrs()
        coreapp.connection.rollback()


class CurrenciesEndPoint(BaseAppTest):

    def test_getCurrencies(self):
        gw = self._gw
        env = gw.env
        env['SCRIPT_NAME'] = ''
        env['PATH_INFO'] = '/currencies'

        gw.run(application)

        correct = json_currencies(coreapp.get_all_currencies())

        self.assertEqual(gw.result_data[0].decode(), correct)

    def test_postCurrenciesRequestSuccessful(self):
        gw = self._gw
        env = gw.env

        new_cur_qry = {'code': 'XXX', 'name': 'some_curr', 'sign': '$#'}

        qry_url_encoded = urlencode({quote(k): quote(v) for k, v in new_cur_qry.items()})

        env['PATH_INFO'] = '/currencies'
        env['REQUEST_METHOD'] = 'POST'
        env['wsgi.input'] = BytesIO(qry_url_encoded.encode())
        env['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'

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
        env['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'

        gw.run(application)

        self.assertEqual(gw.response_status, http_status_enum_to_string(HTTPStatus.CONFLICT))


class CurrencyEndPoint(BaseAppTest):

    def test_getCurrencySuccessful(self):
        gw = self._gw
        env = gw.env

        env['PATH_INFO'] = '/currency/RUB'
        env['REQUEST_METHOD'] = 'GET'

        gw.run(application)
        correct = json_currency(coreapp.get_currency(Currency(None, 'RUB', None, None)))

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

    def test_respondsWNotImplemented(self):
        gw = self._gw
        env = gw.env

        env['PATH_INFO'] = '/currency/XXX'
        env['REQUEST_METHOD'] = 'PUT'

        gw.run(application)

        self.assertEqual(gw.response_status, http_status_enum_to_string(HTTPStatus.NOT_IMPLEMENTED))


class ExchangeRatesEndPoint(BaseAppTest):

    def test_getExchangeRatesSuccessful(self):
        gw = self._gw
        env = gw.env

        env['PATH_INFO'] = '/exchangeRates'
        env['REQUEST_METHOD'] = 'GET'

        coreapp.COMMIT_IF_SUCCESS = True
        gw.run(application)
        coreapp.COMMIT_IF_SUCCESS = False

        correct = []
        for rate in coreapp.get_all_exchange_rates():
            bcurr = coreapp.get_currency(Currency(None, rate.base_currency_code, None, None))
            tcurr = coreapp.get_currency(Currency(None, rate.target_currency_code, None, None))

            er = ExchangeRate(rate.id, bcurr, tcurr, round(rate.rate, 2))

            correct.append(er)

        correct = json_exchange_rates(correct)

        self.assertEqual(
            correct, gw.result_data[0].decode()
        )

    def test_postExchangeRatesSuccessfull(self):
        gw = self._gw
        env = gw.env
        qd = {'baseCurrencyCode': 'USD', 'targetCurrencyCode': 'BTC', 'rate': 5000}

        env['PATH_INFO'] = '/exchangeRates'
        env['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
        env['REQUEST_METHOD'] = 'POST'
        env['wsgi.input'] = BytesIO(urlencode(qd).encode())

        gw.run(application)

        correct_rate = ExchangeRate(
            coreapp.connection.execute('select max(exchange_rate_id) from exchange_rates').fetchone()[0],
            coreapp.get_currency(Currency(None, 'USD', None, None)),
            coreapp.get_currency(Currency(None, 'BTC', None, None)),
            float(5000)
        )

        correct = json_exchange_rate(correct_rate)

        self.assertEqual(gw.result_data[0].decode(), correct)

    def test_postExchangeRatesWhenCurrencyDoesntExistInDb(self):
        gw = self._gw
        env = gw.env
        qd = {'baseCurrencyCode': 'NNN', 'targetCurrencyCode': 'RUB', 'rate': 95}

        env['PATH_INFO'] = '/exchangeRates'
        env['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
        env['REQUEST_METHOD'] = 'POST'
        env['wsgi.input'] = BytesIO(urlencode(qd).encode())

        gw.run(application)

        self.assertEqual(gw.response_status, http_status_enum_to_string(HTTPStatus.NOT_FOUND))


class ExchangeRateEndPoint(BaseAppTest):

    def test_getExchangeRateSuccessful(self):
        gw = self._gw
        env = gw.env

        env['PATH_INFO'] = '/exchangeRate/USDRUB'
        env['REQUEST_METHOD'] = 'GET'

        rate = coreapp.get_exchange_rate(
                CurrencyRate(None, 'USD', 'RUB', None, None, None), strategy=coreapp.main.FIND_RATE_BY_RECIPROCAL
            )

        correct_rate = ExchangeRate(
            rate.id,
            coreapp.get_currency(Currency(None, rate.base_currency_code, None, None)),
            coreapp.get_currency(Currency(None, rate.target_currency_code, None, None)),
            round(rate.rate, 2)
        )

        correct = json_exchange_rate(correct_rate)
        gw.run(application)
        self.assertEqual(correct, gw.result_data[0].decode())

    def test_getOrPostExchangeRateRespondsWBadRequest(self):
        gw = self._gw
        env = gw.env

        inp = ('/USDRUBXXX', '/USDRUB/XXX')

        for url in inp:
            for meth in ('GET', 'PATCH'):
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
        env['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
        env['wsgi.input'] = BytesIO(urlencode(qry_d).encode())

        gw.run(application)

        rate = coreapp.get_exchange_rate(CurrencyRate(None, 'USD', 'RUB', None, None, None))
        correct_rate = ExchangeRate(
            rate.id,
            coreapp.get_currency(Currency(None, 'USD', None, None)),
            coreapp.get_currency(Currency(None, 'RUB', None, None)),
            round(rate.rate, 2)
        )

        correct = json_exchange_rate(correct_rate)

        self.assertEqual(
            correct, gw.result_data[0].decode()
        )

    def test_patchExchangeRateRespondsWNotFound(self):
        gw = self._gw
        env = gw.env

        qry_d = {'rate': 100}
        env['PATH_INFO'] = '/exchangeRate/XXXBBB'
        env['REQUEST_METHOD'] = 'PATCH'
        env['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
        env['wsgi.input'] = BytesIO(urlencode(qry_d).encode())

        gw.run(application)

        self.assertEqual(gw.response_status, http_status_enum_to_string(HTTPStatus.NOT_FOUND))

    def test_respondsWNotImplemented(self):
        gw = self._gw
        env = gw.env

        qry_d = {'rate': 100}
        env['PATH_INFO'] = '/exchangeRate/XXXBBB'
        env['REQUEST_METHOD'] = 'POST'
        env['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
        env['wsgi.input'] = BytesIO(urlencode(qry_d).encode())

        gw.run(application)

        self.assertEqual(gw.response_status, http_status_enum_to_string(HTTPStatus.NOT_IMPLEMENTED))


class ExchangeEndPoint(BaseAppTest):

    def test_getExchangeSuccessful(self):
        gw = self._gw
        env = gw.env
        qd = {'from': 'USD', 'to': 'RUB', 'amount': 10.5}

        env['PATH_INFO'] = '/exchange'
        env['QUERY_STRING'] = urlencode(qd)
        env['REQUEST_METHOD'] = 'GET'
        env['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'

        gw.run(application)

        rateval = json.loads(gw.result_data[0].decode())['convertedAmount']

        correct = coreapp.get_exchange_rate(
            CurrencyRate(None, 'USD', 'RUB', None, None, None)
        ).reduced_rate * qd['amount']

        self.assertEqual(round(correct, 2), rateval)

    def test_respondsWNotFoundIfCurrencyDoesntExistInDB(self):
        gw = self._gw
        env = gw.env
        qds = {'from': 'XXX', 'to': 'RUB', 'amount': 10.5}, {'from': 'USD', 'to': 'XXX', 'amount': 10.5}

        env['PATH_INFO'] = '/exchange'
        env['REQUEST_METHOD'] = 'GET'
        env['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'

        for qd in qds:
            env['QUERY_STRING'] = urlencode(qd)
            gw.run(application)
            self.assertEqual(http_status_enum_to_string(HTTPStatus.NOT_FOUND), gw.response_status)
            gw.clean_attrs()

    def test_respondsWBadRequestIfAmountIsNotNumeric(self):
        gw = self._gw
        env = gw.env
        qd = {'from': 'USD', 'to': 'RUB', 'amount': 'not num'}

        env['PATH_INFO'] = '/exchange'
        env['REQUEST_METHOD'] = 'GET'
        env['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
        env['QUERY_STRING'] = urlencode(qd)

        gw.run(application)
        self.assertEqual(http_status_enum_to_string(HTTPStatus.BAD_REQUEST), gw.response_status)
