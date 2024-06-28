import dataclasses
from functools import partial
from collections import OrderedDict

from .wsgi_application_base import WSGIApplication
import app as coresrv


application = WSGIApplication()


def dataclass_as_specified_dict(dataclass: dataclasses.dataclass, fields: tuple):
    d = OrderedDict()
    for f in fields:
        d[f] = getattr(dataclass, f)
    return d


currency_as_dict = partial(dataclass_as_specified_dict, fields={'id', 'full_name', 'code', 'sign'})


@application.at_route('/currencies')
class CurrenciesHandler(WSGIApplication):

    def doGET(self, env, start_response):
        pass


