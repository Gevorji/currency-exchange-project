import dataclasses
import http.client
import json
from functools import partial
from collections import OrderedDict
from http import HTTPStatus
from urllib.parse import parse_qsl

from .wsgi_application_base import WSGIApplication, http_status_enum_to_string
import app as coresrv
from app.data_objects import Currency, CurrencyRate


application = WSGIApplication()


def dataclass_as_specified_dict(dataclass: dataclasses.dataclass, fields: tuple):
    d = OrderedDict()
    for f in fields:
        d[f] = getattr(dataclass, f)
    return d


def json_dumpb(obj, *args, encoding='utf-8', **kwargs):
    return json.dumps(obj, *args, **kwargs).encode(encoding)


currency_as_dict = partial(dataclass_as_specified_dict, fields=('id', 'full_name', 'code', 'sign'))
exch_rate_as_dict = partial(dataclass_as_specified_dict, fields=('id', 'base_currency_id', 'target_currency_id', 'rate'))


@application.at_route('/currencies')
class CurrenciesHandler(WSGIApplication):

    def doGET(self, env, start_response):
        query_res = [currency_as_dict(curr) for curr in coresrv.get_all_currencies()]
        json_data = json_dumpb(query_res)

        headers = [('Content-Type', 'application/json')]
        start_response(
            http_status_enum_to_string(HTTPStatus.OK),
            headers
        )

        yield json_data

    def doPOST(self, env, start_response):
        if env.get('HTTP_CONTENT_TYPE') != 'application/x-www-form-urlencoded':
            headers = []
            json_data = json_dumpb(
                {'message': 'Required x-www-form-urlencoded'}
            )
            headers.append(('Content-Type', 'application/json'))
            self.do_error_response(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, headers, json_data)

        ql = parse_qsl(env['wsgi.input'].read())


class CurrencyHandler(WSGIApplication):

    def doGET(self, env, start_response):
        path_comps = self._get_path_components(env)
        curr_code = path_comps[0].upper()

        if len(path_comps) != 2:
            headers = []
            json_msg = json_dumpb(
                {'message': 'Exactly one currency code should be provided as an endpoint of this resource'}
            )
            headers.append(('Content-Type', 'text/json'))

            yield from self.do_error_response(HTTPStatus.BAD_REQUEST, headers, start_response, json_msg)
            return

        try:
            curr_query_obj = Currency(None, curr_code, None, None)
        except TypeError:
            headers = []
            json_msg = json_dumpb(
                {'message': 'Invalid currency code (valid is 3 alphabetical characters)'}
            )
            headers.append(('Content-Type', 'text/json'))

            yield from self.do_error_response(
                HTTPStatus.BAD_REQUEST, (('Content-Type', 'text/json'),), start_response, json_msg
            )
            return

        curr_data_obj = coresrv.get_currency(curr_query_obj)

        if not curr_data_obj:
            headers = []
            json_msg = json_dumpb(
                {'message': "Currency wasn't found"}
            )
            headers.append(('Content-Type', 'text/json'))

            yield from self.do_error_response(HTTPStatus.NOT_FOUND, headers, start_response, json_msg)
            return

        json_data = json_dumpb(currency_as_dict(curr_data_obj))

        headers = [('Content-Type', 'textson')]
        start_response(HTTPStatus.OK, headers)

        yield json_data



