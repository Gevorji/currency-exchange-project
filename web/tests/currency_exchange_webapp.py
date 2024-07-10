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


class GetAllCurrencies(unittest.TestCase):
    gw = MockServerGateway(mock_env)

    def setUp(self) -> None:
        self.gw.env = mock_env.copy()

    def tearDown(self) -> None:
        self.gw.clean_attrs()

    def test_GetCurrencies(self):
        env = mock_env.copy()
        env['SCRIPT_NAME'] = ''
        env['PATH_INFO'] = '/currencies'
        gw = MockServerGateway(env)

        gw.run(application)

        correct = json.dumps(list(currency_as_dict(cur) for cur in coreapp.get_all_currencies()))

        self.assertEqual(gw.result_data[0], correct)


