import sys
from collections import namedtuple
from types import FunctionType
from urllib.parse import urlparse, parse_qsl, unquote
from urllib.error import URLError
from typing import Callable, Iterable
from http import HTTPStatus
import re


ResponseContext = namedtuple(
        'ResponseContext',
        ['env', 'headers_set', 'headers_sent', 'orig_start_response', 'own_start_response']
    )


class WSGIApplication:
    _path_pattern = re.compile('(/[a-zA-Z0-9]*)*')

    def __init__(self):
        self._handler_route_map = {}

    def __call__(self, env: dict, start_response: Callable):
        # path validness checking happens here (http error response)
        path = env.get('PATH_INFO')
        path_components: list = self._get_path_components(env)

        if not self._is_valid_path(path):
            raise ResponseProcessingError(HTTPStatus.BAD_REQUEST)

        inner_handler = self._get_inner_handler(env['REQUEST_METHOD'])

        self.set_new_response_context(env, start_response)

        try:
            if inner_handler:
                result = inner_handler()
                yield from self.start_response_giveaway(result)
                return

            elif len(path_components) == 1:
                raise ResponseProcessingError(HTTPStatus.NOT_IMPLEMENTED)
        except Exception as e:
            yield from self.do_error_response(e)
            return

        try:
            yield from self._delegate_wsgi_call(env, start_response)
            return
        except Exception as e:
            yield from self.do_error_response(e)
            return

    def _delegate_wsgi_call(self, env: dict, start_response: Callable):
        path_components = self._get_path_components(env)

        handler = self._get_handler(f'/{path_components[1]}')

        if handler:
            new_env = env.copy()
            new_env['SCRIPT_NAME'] = '/' + path_components[1]
            new_env['PATH_INFO'] = '/' + '/'.join(path_components[2:])

            return handler(new_env, start_response)

        supplied = ', '.join(self._handler_route_map.keys())
        raise ResponseProcessingError(
            HTTPStatus.NOT_FOUND, f'Cant serve request to {env["SCRIPT_NAME"]}. Supplied paths on this app: {supplied}'
        )

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
            cls = None
            if not isinstance(handler, FunctionType):
                if issubclass(handler, self.__class__):  # place an instance if decorated a class
                    cls = handler
                    handler = handler()
                else:
                    raise AssertionError(
                        'Handler, if is implemented as a class, must be a descendant of WSGIApplication'
                    )
            self._handler_route_map[path] = handler
            if not case_sensitive:
                self._handler_route_map[path.lower()] = handler
                self._handler_route_map[path.upper()] = handler
            return cls or handler

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

    def make_own_start_response(self, headers_set: list, headers_sent: list):

        def start_response(status, headers, exc_info=None):
            nonlocal headers_set, headers_sent
            if exc_info:
                try:
                    if headers_sent:
                        # Re-raise original exception if headers sent
                        raise exc_info[1].with_traceback(exc_info[2])
                finally:
                    exc_info = None
            elif headers_set:
                raise AssertionError("Headers already set!")

            headers_set[:] = status, headers

        return start_response

    def modify_headers(self, env, headers):
        pass

    def modify_error_response_headers(self, e, headers):
        pass

    def process_data(self, data):
        return data

    def process_status(self, status):
        return status

    def do_error_response(self, e):
        rc = self.resp_ctxt
        env, headers = rc.env, rc.headers_set
        if isinstance(e, ResponseProcessingError):
            status = e.status
            msg = e.msg
        else:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            msg = e.args[0]

        if headers and isinstance(headers[0], HTTPStatus):
            headers = headers[1:]
        self.modify_error_response_headers(e, headers)
        rc.orig_start_response(status, headers, sys.exc_info())

        yield msg

    def start_response_giveaway(self, result):
        rc = self.resp_ctxt
        env, headers_set, headers_sent = rc.env, rc.headers_set, rc.headers_sent
        for datapiece in result:
            if not headers_set:
                raise AssertionError('Write before start_response()')
            if not headers_sent:
                status, headers_sent = headers_set[:]
                self.modify_headers(env, headers_sent)
                if not isinstance(status, HTTPStatus):
                    raise AssertionError('Status supposed to be an HTTPStatus enum member here')
                rc.orig_start_response(self.process_status(status), list(headers_set))
            yield self.process_data(datapiece)

    def set_new_response_context(self, env, start_response):
        headers_set = []
        headers_sent = []
        stresp = self.make_own_start_response(headers_set, headers_sent)
        self.resp_ctxt = ResponseContext(env, headers_set, headers_sent, start_response, stresp)
        return self.resp_ctxt

class ResponseProcessingError(Exception):
    """Raised by internal procedures for generalized error response constructing"""
    def __init__(self, status: HTTPStatus, msg: str = ''):
        self.status = status
        self.msg = msg

