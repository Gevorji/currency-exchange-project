

class RequestDispathcer:

    def __init__(self):
        self._routes_mappings = {}

    def route(self, path: str):

        def bind_route(handler):
            self._routes_mappings[path] = handler
            return handler

        return bind_route

    def dispatch(self, request):
        path_info = request.get('path_info')

        handler = self._routes_mappings[path_info]

        handler()

