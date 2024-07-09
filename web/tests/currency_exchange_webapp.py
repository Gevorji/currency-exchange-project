import unittest
import os
import sys
import subprocess
import urllib.error
from urllib.request import urlopen, Request
from urllib.parse import urlunparse, ParseResult
from http import HTTPStatus
import json

import app as coreapp

sinf = subprocess.STARTUPINFO(dwFlags=subprocess.CREATE_NEW_CONSOLE)
pr = subprocess.Popen(['python', 'test_server.py'], startupinfo=sinf)

server_adr = 'localhost:8000'
scheme = 'http'

urlbase = ('http', 'localhost:8000', '', )


def build_url(path='', query=''):
    return urlunparse(ParseResult('http', 'localhost:8000', path, '', query, ''))


def do_request(req: Request):
    try:
        res = urlopen(req)
    except urllib.error.HTTPError as e:
        sys.stderr.write(f'{e.code}')
        sys.stderr.write(f'{e.read()}')
        return e


class GetAllCurrencies(unittest.TestCase):

    def test_GetCurrencies(self):
        req = Request(build_url('/currencies'))
        res = do_request(req)

        code, headers, body = res.code, res.headers, res.read().decode()

        correct = list(coreapp.get_all_currencies())

        self.assertEqual(json.loads(body), correct)


