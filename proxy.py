#!/usr/bin/python

import SimpleHTTPServer
import SocketServer
import httplib
import logging
import subprocess
import sys

PORT = 80


class ServerHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def do_GET(self):
        logging.warning("======= GET STARTED =======")
        logging.warning(self.headers)
        url = "http://" + self.headers.getheader('host') + self.path
        self.make_http_request("GET", url)

    def do_POST(self):
        logging.warning("======= POST STARTED =======")
        logging.warning(self.headers)
        length = int(self.headers.getheader('content-length'))
        data = self.rfile.read(length)
        logging.warning("======= POST VALUES =======")
        logging.warning(data)
        logging.warning("\n")
        url = "http://" + self.headers.getheader('host') + self.path
        self.make_http_request("POST", url, data)
        # SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

    def resolve_host(self, host):
        out, error = self.exec_command("nslookup %s - 8.8.8.8" % host)
        found = False
        for line in out.split("\n"):
            if found:
                ip = line.split(" ")[1]
                print "returning ip", ip
                return ip
            if line.startswith(host) and "canonical name" in line:
                host = line.split(" ")[-1][:-1]
            if line.endswith(host):
                found = True
        print lines
        print "returning input", host
        return host

    def exec_command(self, command):
        print "====>", command
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, error) = proc.communicate()
        if error:
            print >> sys.stderr, error
        return out, error

    def make_http_request(self, method, url, data=None):
        print "requesting {0}: {1}".format(method, url)
        print "data: {0}".format(data)
        parts = url.split("/")
        host = parts[2].split(":")[0]
        host = self.resolve_host(host)
        print host
        path = "/" + "/".join(parts[3:])
        if url.startswith("https://"):
            conn = httplib.HTTPSConnection(host)
        else:
            conn = httplib.HTTPConnection(host)
        conn.request(method, path, data, self.headers.dict)
        response = conn.getresponse()
        print response.status, response.reason
        content = response.read()
        conn.close()
        print "==> {0}".format(content[:256])

        self.send_response(response.status)
        for header in response.msg.headers:
            self.wfile.write(header)
        self.end_headers()
        self.wfile.write(content)
        self.wfile.close()


class Server:
    def __init__(self, port, handler):
        self.port = port
        self.handler = handler
        self.httpd = SocketServer.TCPServer(("", self.port), self.handler)

    def main_loop(self):
        print "serving at port", self.port
        self.httpd.serve_forever()

    def shutdown(self):
        self.httpd.shutdown()


if __name__ == '__main__':
    handler = ServerHandler
    server = Server(PORT, handler)

    try:
        server.main_loop()
    except KeyboardInterrupt:
        print "Ctrl C - Stopping server"
        sys.exit(1)
    finally:
        server.shutdown()
