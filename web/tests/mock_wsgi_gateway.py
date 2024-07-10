class MockServerGateway:

    def __init__(self, env):
        self. headers_stored = []
        self.headers_sent = []
        self.response_status = None
        self.env = env
        self.result_data = []

    def run(self, application):

        env = self.env

        def write(data: bytes):

            if not self.headers_stored:
                raise AssertionError("write() before start_response()")

            if not self.headers_sent:
                self.response_status, self.response_headers = self.headers_stored
                self.headers_sent = self.headers_stored

            self.result_data.append(data)

        def start_response(status, headers, exc_info=None):

            if exc_info:
                try:
                    if self.headers_sent:
                        raise exc_info[1].with_traceback(exc_info[2])
                finally:
                    exc_info = None

            if self.headers_stored:
                raise AssertionError(
                    'Headers already set. Second call to start_response() should provide an exception.'
                )

            self.headers_stored.append(status)
            self.headers_stored.append(headers)

            return write

        response = application(env, start_response)

        try:
            for data in response:
                if data:
                    write(data)
            if not self.headers_sent:
                write(b'')
        finally:
            if hasattr(response, 'close'):
                response.close()

    def clean_attrs(self):
        self.__init__(self.env)