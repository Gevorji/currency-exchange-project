import json
import sys
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
        # self._get_handler == None is True -> 404 Not found
        path = env.get('PATH_INFO')
        path_components: list = self._get_path_components(env)

        if not self._is_valid_path(path):
            start_response(http_status_enum_to_string(HTTPStatus.BAD_REQUEST), [])
            return tuple()

        if len(path_components) == 1:
            method_name = env['REQUEST_METHOD']
            handler = getattr(self, f'do{method_name}', None)

            if not handler:
                start_response(http_status_enum_to_string(HTTPStatus.NOT_IMPLEMENTED), [])
                return tuple()

            result = self.call_with_exception_catch(handler, env, start_response)
            return result if result else tuple()

        new_env = env.copy()
        new_env['SCRIPT_NAME'] = '/' + path_components[1]
        new_env['PATH_INFO'] = '/' + '/'.join(path_components[2:])

        return self._delegate_wsgi_call(new_env, start_response)

    def _delegate_wsgi_call(self, env: dict, start_response: Callable):

        handler = self._get_handler(env['SCRIPT_NAME'])

        if not handler:
            start_response(http_status_enum_to_string(HTTPStatus.NOT_FOUND), [('Content-Type', 'text/plain')])
            supplied = ', '.join(self._handler_route_map.keys())
            return (f'Cant serve request to {env["SCRIPT_NAME"]}. Supplied paths on this app: {supplied}'.encode(),)

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
            if issubclass(handler, self.__class__):  # place an instance if decorated a class
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
        start_response(http_status_enum_to_string(code), headers)

        if msg:
            yield json.dumps({'message': msg}).encode()
        else:
            return

    def _parse_qsl(self, env: dict, required_fields: list | tuple = None) -> dict:
        if env.get('HTTP_CONTENT_TYPE') != 'application/x-www-form-urlencoded':
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

        except ValueError:
            raise ResponseProcessingError(HTTPStatus.BAD_REQUEST, 'Bad x-www-form-urlencoded')
        except AssertionError:
            raise ResponseProcessingError(
                HTTPStatus.BAD_REQUEST, 'Not enough or too many parameters, or wrong parameter name'
            )
        except UnicodeDecodeError:
            raise ResponseProcessingError(HTTPStatus.UNPROCESSABLE_ENTITY, 'Was not able to decode body')

        return qd



class ResponseProcessingError(Exception):
    """Raised by internal procedures for generalized error response constructing"""
    def __init__(self, status: HTTPStatus, msg: str):
        self.args = status, msg

