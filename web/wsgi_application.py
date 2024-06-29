import dataclasses
import json
from functools import partial
from collections import OrderedDict
from http import HTTPStatus

from wsgi_application_base import WSGIApplication, http_status_enum_to_string
import app as coresrv


application = WSGIApplication()


def dataclass_as_specified_dict(dataclass: dataclasses.dataclass, fields: tuple):
    d = OrderedDict()
    for f in fields:
        d[f] = getattr(dataclass, f)
    return d


currency_as_dict = partial(dataclass_as_specified_dict, fields=('id', 'full_name', 'code', 'sign'))
exch_rate_as_dict = partial(dataclass_as_specified_dict, fields=('id', 'base_currency_id', 'target_currency_id', 'rate')

@application.at_route('/currencies')
class CurrenciesHandler(WSGIApplication):

    def doGET(self, env, start_response):
        query_res = [currency_as_dict(curr) for curr in coresrv.get_all_currencies()]
        json_data = json.dumps(query_res)

        start_response(
            http_status_enum_to_string(HTTPStatus.OK),
            (
                ('Content-Type', 'application/json'),
            )
        )

        yield response


