from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit
import os.path

server_address = ('', 8000)



class RequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        url = urlsplit(self.path)

        if os.path.exists(url.path):
            pass

        else:
            self.send_error(404)
            self.send_header()



