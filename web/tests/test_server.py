from wsgiref.simple_server import make_server
import sys
sys.path.insert(0, r'C:\Users\user\Desktop\currency-exchange-project')

from web.wsgi_application import application

server = make_server('localhost', 8000, application)

print(__name__)

if __name__ == '__main__':
    print('here')
    server.serve_forever()
