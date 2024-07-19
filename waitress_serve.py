from waitress import serve

from web.wsgi_application import application

application.set_logging_level('DEBUG')

if __name__ == '__main__':
    serve(application, host='localhost', port=8000, expose_tracebacks=True, threads=1)
