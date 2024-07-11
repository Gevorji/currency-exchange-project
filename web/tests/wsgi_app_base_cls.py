from unittest import TestCase
from urllib.parse import urlencode, quote
from io import BytesIO
from http import HTTPStatus

from currency_exchange_webapp import BaseAppTest
from web.wsgi_application_base import WSGIApplication, ResponseProcessingError

testapp = WSGIApplication()


class ParseURLEncodedQuery(BaseAppTest):

    def test_parsesSuccessfully(self):
        inp = (dict((('name', 'John'), ('surname', 'Doe'))), {'язык': 'русский'}, {quote('smile/'): quote('=)')})

        mockenv = {'HTTP_CONTENT_TYPE': 'application/x-www-form-urlencoded', }

        for qd in inp:
            query = urlencode({quote(k): quote(v) for k, v in qd.items()})
            mockenv['wsgi.input'] = BytesIO(query.encode())
            with self.subTest(query=qd):
                self.assertEqual(qd, testapp._parse_qsl(mockenv))

    def test_raisesErrorIfNotExactParametersSupplied(self):
        inp = (
        {'name': 'John', 'surname': 'Doe', 'job': 'DBA'}, {'name': 'John', 'onemorename': 'Doe'}, {'name': 'John'})

        for qd in inp:
            query = urlencode(qd).encode()
            mockenv = {'HTTP_CONTENT_TYPE': 'application/x-www-form-urlencoded', 'wsgi.input': BytesIO(query)}
            with self.subTest(query=qd):
                with self.assertRaises(ResponseProcessingError) as exctxt:
                    testapp._parse_qsl(mockenv, required_fields=('name', 'surname'))
                self.assertEqual(exctxt.exception.args[0], HTTPStatus.BAD_REQUEST)

    def test_raisesErrorIfURLQueryIsBadlyEncoded(self):
        inp = ('', 'val', 'val%FF')

        mockenv = {'HTTP_CONTENT_TYPE': 'application/x-www-form-urlencoded'}

        for query in inp:
            mockenv['wsgi.input'] = BytesIO(query.encode())
            with self.subTest(query=query):
                with self.assertRaises(ResponseProcessingError) as exctxt:
                    testapp._parse_qsl(mockenv)
                self.assertEqual(exctxt.exception.args[0], HTTPStatus.BAD_REQUEST)
                self.assertEqual(exctxt.exception.args[1], 'Bad x-www-form-urlencoded')
