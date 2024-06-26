from urllib.parse import urlparse
from urllib.error import URLError
import re


class WSGIApplication:
    _path_patter = re.compile('(/[a-zA-Z0-9]*)+')

    def __init__(self):
        self._handler_route_map = {}

    def __call__(self, env, start_response):
        # path validness checking happens here (http error response)
        pass

    def _get_handler(self, path):
        return self._handler_route_map.get('path')

    def at_route(self, path):
        if not self._is_valid_path(path):
            raise URLError(f'{path} is invalid path')

        def recorder(handler):
            self._handler_route_map['path'] = handler
            return handler

        return recorder

    def _is_valid_path(self, path: str):
        return True if self._path_patter.fullmatch(path) else False
