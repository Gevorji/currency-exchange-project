from unittest import TestCase
from urllib.parse import urlencode, quote
from io import BytesIO
from http import HTTPStatus

from currency_exchange_webapp import BaseAppTest
from web.wsgi_application_base import WSGIApplication, ResponseProcessingError

testapp = WSGIApplication()


@testapp.at_route('/currency')
def mock_currency_handler(env, start_response):
    start_response('200 OK', ['text/plain'])
    return [b'Hello!']


@testapp.at_route('/currencies')
def mock_currencies_handler(env, start_response):
    start_response('200 OK', ['text/plain'])
    return [b'Hello! Test!']


class ParseURLEncodedQuery(BaseAppTest):

    def test_parsesSuccessfully(self):
        inp = (
            dict((('name', 'John'), ('surname', 'Doe'))),
            {'язык': 'русский'}, {quote('smile/'): quote('=)')}
        )

        mockenv = {'CONTENT_TYPE': 'application/x-www-form-urlencoded', }

        for qd in inp:
            query = urlencode({quote(k): quote(v) for k, v in qd.items()})
            mockenv['wsgi.input'] = BytesIO(query.encode())
            with self.subTest(query=qd):
                self.assertEqual(qd, testapp._parse_qsl(mockenv))

    def test_raisesErrorIfNotExactParametersSupplied(self):
        inp = (
        {'name': 'John', 'surname': 'Doe', 'job': 'DBA'},
        {'name': 'John', 'onemorename': 'Doe'},
        {'name': 'John'}
        )

        for qd in inp:
            query = urlencode(qd).encode()
            mockenv = {'CONTENT_TYPE': 'application/x-www-form-urlencoded', 'wsgi.input': BytesIO(query)}
            with self.subTest(query=qd):
                with self.assertRaises(ResponseProcessingError) as exctxt:
                    testapp._parse_qsl(mockenv, required_fields=('name', 'surname'))
                self.assertEqual(exctxt.exception.args[0], HTTPStatus.BAD_REQUEST)

    def test_raisesErrorIfURLQueryIsBadlyEncoded(self):
        inp = ('', 'val', 'val%FF')

        mockenv = {'CONTENT_TYPE': 'application/x-www-form-urlencoded'}

        for query in inp:
            mockenv['wsgi.input'] = BytesIO(query.encode())
            with self.subTest(query=query):
                with self.assertRaises(ResponseProcessingError) as exctxt:
                    testapp._parse_qsl(mockenv)
                self.assertEqual(exctxt.exception.args[0], HTTPStatus.BAD_REQUEST)
                self.assertEqual(exctxt.exception.args[1], 'Bad x-www-form-urlencoded')

    def test_raisesErrorIfBytesMalformed(self):
        mockenv = {
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'wsgi.input': BytesIO(b'\x08\xFF\xDD\x0F')
        }
        with self.assertRaises(ResponseProcessingError) as exctxt:
            testapp._parse_qsl(mockenv)
        self.assertEqual(exctxt.exception.args[0], HTTPStatus.UNPROCESSABLE_ENTITY)


class RootRespondsWSuccessStatuses(BaseAppTest):

    def test_RootRespondsWOkOnUnusualURIs(self):
        inp = ('///currencies', '/currency////RUB')

        for path_inf in inp:
            self._gw.env['PATH_INFO'] = path_inf
            self._gw.run(testapp)
            with self.subTest(PATH_INFO=path_inf):
                self.assertEqual(self._gw.response_status, '200 OK')
            self._gw.clean_attrs()


class RootHandlerRespondsWithErrors(BaseAppTest):

    def test_RootRespondsWNotImplemented(self):
        inp = (('/', 'GET'), ('/', 'POST'))
        for path_inf, meth in inp:
            with self.subTest(PATH_INFO=path_inf, METHOD=meth):
                self._gw.env['PATH_INFO'] = path_inf
                self._gw.env['REQUEST_METHOD'] = meth
                self._gw.run(testapp)
                self.assertEqual(self._gw.response_status, '501 Not Implemented')
            self._gw.clean_attrs()
