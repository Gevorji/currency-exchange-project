import unittest
import os
import sys
import json
import wsgiref
import wsgiref.util

import app as coreapp
from web.tests.mock_wsgi_gateway import MockServerGateway
from web.wsgi_application import application, currency_as_dict, exch_rate_as_dict

mock_env = {}

wsgiref.util.setup_testing_defaults(mock_env)

application.set_logging_level('DEBUG')

gw = MockServerGateway(mock_env)


class BaseAppTest(unittest.TestCase):
    _gw = gw

    def setUp(self) -> None:
        self._gw.env = mock_env.copy()

    def tearDown(self) -> None:
        self._gw.clean_attrs()


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


class GetAllCurrencies(BaseAppTest):

    def test_getCurrencies(self):
        env = mock_env.copy()
        env['SCRIPT_NAME'] = ''
        env['PATH_INFO'] = '/currencies'
        gw = MockServerGateway(env)

        gw.run(application)

        correct = json.dumps(list(currency_as_dict(cur) for cur in coreapp.get_all_currencies()))

        self.assertEqual(gw.result_data[0].decode(), correct)

    def test_postCurrenciesRequestSuccessful(self):
        pass


