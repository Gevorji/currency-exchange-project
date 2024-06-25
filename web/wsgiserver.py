from http.server import HTTPServer, BaseHTTPRequestHandler


class WSGIServerRequestHandler(BaseHTTPRequestHandler):

    def build_environment(self):
        env = {
            'REQUEST_METHOD': self.command,
            'CONTENT_LENGTH': self.headers.get('Content-Length', ''),
            'CONTENT_TYPE': self.headers.get('Content-Type', '')
        }

        for kw, val in self.headers.items():
            env_param_name = f'HTTP_{kw.upper().replace("-", "_")}'
            env[env_param_name] = val

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

                if headers_stored:
                    raise exc_info[1].with_traceback(exc_info[2])

            headers_stored.append(status)
            headers_stored.append(headers)

            return write

        response = application(env, start_response)

        try:
            for data in response:
                write(data)
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
    server = HTTPServer(('localhost', 8080), WSGIServerRequestHandler)
    print(f'serving at: {server.socket.getsockname()}')
    server.serve_forever()


