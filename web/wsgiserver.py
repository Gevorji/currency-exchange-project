import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse


class WSGIServerRequestHandler(BaseHTTPRequestHandler):

    def build_environment(self):
        url_components = urlparse(self.path)

        env = {
            'REQUEST_METHOD': self.command,
            'CONTENT_LENGTH': self.headers.get('Content-Length', ''),
            'CONTENT_TYPE': self.headers.get('Content-Type', ''),
            'SCRIPT_NAME': '',
            'PATH_INFO': self.path,
            'QUERY_STRING': url_components.query,
            'SERVER_NAME': 'Python http.server',
            'SERVER_PORT': f'{self.server.server_address[0]}:{self.server.server_address[1]}',
            'SERVER_PROTOCOL': self.protocol_version,
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'http',
            'wsgi.input': self.rfile,
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': False,
            'wsgi_run_once': False
        }

        for kw, val in self.headers.items():
            env[f'HTTP_{kw.upper().replace("-", "_")}'] = val

        return env

    def run_with_cgi(self, application):

        env = self.build_environment()

        headers_stored = []
        headers_sent = []

        def write(data: bytes):

            if not headers_stored:
                raise AssertionError("write() before start_response()")

            nonlocal headers_sent

            out = self.wfile

            if not headers_sent:
                status, response_headers = headers_stored
                headers_sent = headers_stored
                code, msg = status.split()
                code = int(code)
                if code >= 400:
                    self.send_error(code, msg)
                else:
                    self.send_response(code, msg)

                for kw, value in response_headers:
                    self.send_header(kw, value)

                self.end_headers()

            out.write(data)

        def start_response(status, headers, exc_info=None):

            if exc_info:
                try:
                    if headers_sent:
                        raise exc_info[1].with_traceback(exc_info[2])
                finally:
                    exc_info = None

            if headers_stored:
                raise AssertionError(
                    'Headers already set. Second call to start_response() should provide an exception.'
                )

            headers_stored.append(status)
            headers_stored.append(headers)

            return write

        response = application(env, start_response)

        try:
            for data in response:
                if data:
                    write(data)
            if not headers_sent:
                write(b'')
        finally:
            if hasattr(response, 'close'):
                response.close()

    def do_GET(self):
        self.send_response(200, 'OK')
        self.send_header('Content-Type', 'text/plain')
        response = repr(self.build_environment()).encode()

        self.send_header('Content-Length', str(len(response)))

        self.end_headers()

        self.wfile.write(response)



if __name__ == '__main__':
    server = HTTPServer(('localhost', 80), WSGIServerRequestHandler)
    print(f'serving at: {server.socket.getsockname()}')
    server.serve_forever()


