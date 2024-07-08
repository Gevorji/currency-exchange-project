import unittest
import os
import subprocess
from urllib.request import urlopen, Request
from urllib.parse import urljoin
from http import HTTPStatus
import json

import app as coreapp

sinf = subprocess.STARTUPINFO(dwFlags=subprocess.CREATE_NEW_CONSOLE)
pr = subprocess.Popen(['python', 'test_server.py'], startupinfo=sinf)

server_adr = 'localhost:8000'
scheme = 'http'


class GetAllCurrencies(unittest.TestCase):

    def test_GetCurrencies(self):
        req = Request(server_adr + '/currencies')
        res = urlopen(req)

        code, headers, body = res.code, res.headers, res.read().decode()

        correct = list(coreapp.get_all_currencies())

        self.assertEqual(json.loads(body), correct)


