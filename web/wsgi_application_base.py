import json
import sys
from types import FunctionType
from urllib.parse import urlparse, parse_qsl, unquote
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
        path = env.get('PATH_INFO')
        path_components: list = self._get_path_components(env)

        if not self._is_valid_path(path):
            start_response(http_status_enum_to_string(HTTPStatus.BAD_REQUEST), [])
            return tuple()

        handler = self._get_inner_handler(env['REQUEST_METHOD'])

        if handler:
            result = self.call_with_exception_catch(handler, env, start_response)
            return result if result else tuple()

        elif len(path_components) == 1:
            start_response(http_status_enum_to_string(HTTPStatus.NOT_IMPLEMENTED), [])
            return tuple()

        return self._delegate_wsgi_call(env, start_response)

    def _delegate_wsgi_call(self, env: dict, start_response: Callable):
        path_components = self._get_path_components(env)

        handler = self._get_handler(f'/{path_components[1]}')

        if handler:
            new_env = env.copy()
            new_env['SCRIPT_NAME'] = '/' + path_components[1]
            new_env['PATH_INFO'] = '/' + '/'.join(path_components[2:])

            return self.call_with_exception_catch(handler, new_env, start_response)

        start_response(http_status_enum_to_string(HTTPStatus.NOT_FOUND), [('Content-Type', 'text/plain')])
        supplied = ', '.join(self._handler_route_map.keys())
        return (f'Cant serve request to {env["SCRIPT_NAME"]}. Supplied paths on this app: {supplied}'.encode(),)

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
            if not isinstance(handler, FunctionType):
                if issubclass(handler, self.__class__):  # place an instance if decorated a class
                    handler = handler()
                else:
                    raise AssertionError(
                        'Handler, if is implemented as a class, must be a descendant of WSGIApplication'
                    )
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
        path_str = env.get('PATH_INFO')
        if path_str == '/':
            path_str = ''

        path_comps = path_str.split('/')
        path_comps = list(filter(None, path_comps))
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
        start_response(http_status_enum_to_string(code), headers, sys.exc_info())

        if msg:
            yield json.dumps({'message': msg}).encode()
        else:
            return

    def _parse_qsl(self, env: dict, required_fields: list | tuple = None) -> dict:
        if env.get('CONTENT_TYPE') != 'application/x-www-form-urlencoded':
            raise ResponseProcessingError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, 'Required x-www-form-urlencoded')

        try:
            qd = dict(tuple(
                    (unquote(k), unquote(v)) for k, v in parse_qsl(
                        env['wsgi.input'].read().decode(), strict_parsing=True
                    )
                )
            )

            if required_fields:
                if set(required_fields) != set(qd.keys()):
                    raise AssertionError()
            if not qd:
                raise ValueError

        except ValueError as e:
            if isinstance(e, UnicodeDecodeError):
                raise ResponseProcessingError(HTTPStatus.UNPROCESSABLE_ENTITY, 'Was not able to decode body')
            raise ResponseProcessingError(HTTPStatus.BAD_REQUEST, 'Bad x-www-form-urlencoded')
        except AssertionError:
            raise ResponseProcessingError(
                HTTPStatus.BAD_REQUEST, 'Not enough or too many parameters, or wrong parameter name'
            )

        return qd

    def _get_inner_handler(self, method_name: str):
        return getattr(self, f'do{method_name}', None)

class ResponseProcessingError(Exception):
    """Raised by internal procedures for generalized error response constructing"""
    def __init__(self, status: HTTPStatus, msg: str):
        self.args = status, msg

