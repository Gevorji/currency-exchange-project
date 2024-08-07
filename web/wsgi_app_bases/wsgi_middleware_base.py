from web.wsgi_app_bases.wsgi_application_base import WSGIApplication


class WSGIMiddleware(WSGIApplication):

    def __init__(self, underlying_layer):
        super().__init__()
        self.underlying_layer = underlying_layer

    def __call__(self, env, start_response):

        self.set_new_response_context(env, start_response)

        result = self.run_underlying_app(env, self.resp_ctxt.own_start_response)

        yield from self.start_response_giveaway(result)

    def run_underlying_app(self, env, start_response):
        return self.underlying_layer(env, start_response)

