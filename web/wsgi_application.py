import sys
from urllib.parse import urlparse
from urllib.error import URLError
from typing import Callable, Iterable
from http import HTTPStatus
import re


def http_status_enum_to_string(status: HTTPStatus):
    return f'{status.value} {status.phrase}'


class WSGIApplication:
    _path_pattern = re.compile('(/[a-zA-Z0-9]*)+')

    def __init__(self):
        self._handler_route_map = {}

    def __call__(self, env: dict, start_response: Callable):
        # path validness checking happens here (http error response)
        # self._get_handler == None is True -> 404 Not found
        path = env.get('PATH_INFO')

        handler = self._get_handler(path)

        if not handler:
            start_response(http_status_enum_to_string(HTTPStatus.NOT_FOUND), [])

        try:
            response: Iterable = handler(env, start_response)
        except Exception:
            start_response(http_status_enum_to_string(HTTPStatus.INTERNAL_SERVER_ERROR), [], sys.exc_info())
        else:
            return response

    def _get_handler(self, path):
        return self._handler_route_map.get('path')

    def at_route(self, path):
        if not self._is_valid_path(path):
            raise URLError(f'{path} is invalid path')

        def recorder(handler):
            if not hasattr(handler, '__call__'):
                raise TypeError('Handler should be callable')
            self._handler_route_map['path'] = handler
            return handler

        return recorder

    def _is_valid_path(self, path: str):
        return True if self._path_pattern.fullmatch(path) else False
