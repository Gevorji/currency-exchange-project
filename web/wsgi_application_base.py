import json
import sys
from urllib.parse import urlparse
from urllib.error import URLError
from typing import Callable, Iterable
from http import HTTPStatus
import re


def http_status_enum_to_string(status: HTTPStatus):
    return f'{status.value} {status.phrase}'


class WSGIApplication:
    _path_pattern = re.compile('(/[a-zA-Z0-9]*)*')

    def __init__(self):
        self._handler_route_map = {}

    def __call__(self, env: dict, start_response: Callable):
        # path validness checking happens here (http error response)
        # self._get_handler == None is True -> 404 Not found
        path = env.get('PATH_INFO')

        if not self._is_valid_path(path):
            start_response(http_status_enum_to_string(HTTPStatus.BAD_REQUEST), tuple())
            return tuple()

        if path == '/':
            method_name = env['REQUEST_METHOD']
            handler = getattr(self, f'do{method_name}')

            if not handler:
                start_response(http_status_enum_to_string(HTTPStatus.NOT_IMPLEMENTED), tuple)
                return tuple()

            result = self.call_with_exception_catch(handler, env, start_response)

            return result if result else tuple()

        else:
            return self._delegate_wsgi_call(env, start_response)

    def _delegate_wsgi_call(self, env: dict, start_response: Callable):
        path_components: list = self._get_path_components(env)

        new_env = env.copy()
        new_env['SCRIPT_NAME'] = '/' + path_components[1]
        new_env['PATH_INFO'] = '/'.join(path_components[2:])

        handler = self._get_handler(new_env['SCRIPT_NAME'])

        if not handler:
            start_response(http_status_enum_to_string(HTTPStatus.NOT_FOUND), tuple())
            return tuple()

        result = self.call_with_exception_catch(handler, env, start_response)

        return result if result else tuple()

    def _get_handler(self, path: str):
        if path == '':
            path = '/'

        return self._handler_route_map.get(path)

    def at_route(self, path, case_sensitive=False):
        if not self._is_valid_path(path):
            raise URLError(f'{path} is invalid path')
        if path == '':
            path = '/'

        def recorder(handler):
            if not hasattr(handler, '__call__'):
                raise TypeError('Handler should be callable')
            if issubclass(self.__class__, handler):  # place an instance if decorated a class
                handler = handler()
            self._handler_route_map[path] = handler
            if not case_sensitive:
                self._handler_route_map[path.lower()] = handler
                self._handler_route_map[path.upper()] = handler
            return handler

        return recorder

    def _is_valid_path(self, path: str):
        return True if self._path_pattern.fullmatch(path) else False

    @staticmethod
    def _get_path_components(env):
        path_str = env.get('path')
        path_comps = path_str.split('/')

        if not path_comps[0] != '':
            path_comps.insert(0, '')

        return path_comps

    def call_with_exception_catch(self, func, env: dict, start_response: Callable):
        try:
            response: Iterable = func(env, start_response)
        except Exception:
            start_response(http_status_enum_to_string(HTTPStatus.INTERNAL_SERVER_ERROR), [], sys.exc_info())
        else:
            return response

    def do_json_error_response(self, code: HTTPStatus, headers: list, start_response, msg=None):

        headers.append(('Content-Type', 'application/json'))
        start_response(http_status_enum_to_string(code), headers)

        if msg:
            yield json.dumps({'message': msg}).encode()
        else:
            return


