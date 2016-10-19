#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import sys
import threading
import time
import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCServer

logging.basicConfig(filename='/tmp/pr.log')

client_port = 6969
server_port = 16969


class CQuickXMLRPCServer(threading.Thread, SimpleXMLRPCServer, object):

    def __init__(self, port, bind='0.0.0.0', *args, **kwargs):
        kwargs.setdefault('allow_none', True)

        threading.Thread.__init__(self)
        SimpleXMLRPCServer.__init__(self, (bind, port), *args, **kwargs)

        if kwargs.get('register_introspection_functions', True):
            self.register_introspection_functions()

        if kwargs.get('register_multicall_function', True):
            self.register_multicall_functions()

        self.client_address = None

    def run(self):
        self.serve_forever()

    def process_request(self, request, client_address):
        self.client_address = client_address
        return super(CQuickXMLRPCServer, self).process_request(request, client_address)


class PRServer(CQuickXMLRPCServer):
    
    def __init__(self, *args, **kwargs):
        super(PRServer, self).__init__(*args, **kwargs)
        self.max_failures = 10
        self.host_failures = {}

        self.register_function(self.register)
        self.register_function(self.deregister)
        self.register_function(self.message)
        self.register_function(self.list_peers)

    def list_peers(self):
        return self.host_failures.keys()

    def register(self, address=None):
        address = address or self.client_address
        if address and address not in self.host_failures:
            self.host_failures[address[0]] = 0
    
    def deregister(self, host):
        if host in self.host_failures:
            del self.host_failures[host]

    def _send_single(self, host, summary, description):
        try:
            prd = xmlrpclib.ServerProxy('http://{}:{}'.format(host, client_port))
            prd.message(summary, description)

        except Exception as e:
            logging.error("Could not deliver to {}: {}".format(host, e))
            self.host_failures[host] += 1

    def message(self, summary='PA', description=''):

        # Auto-register on first message
        self.register(address=self.client_address)

        threads = {}
        for host in self.host_failures.iterkeys():
            ht = threading.Thread(target=self._send_single, args=(host, summary, description))
            threads[host] = ht
            ht.start()

        for host, ht in threads.iteritems():
            ht.join(3.0)
            if ht.isAlive():
                self.host_failures[host] += 1

        for host, failures in dict(self.host_failures).iteritems():
            if failures >= self.max_failures:
                logging.info("{} has let us down too many times".format(host))
                del self.host_failures[host]

if __name__ == "__main__":

    server = PRServer(port=server_port)
    server.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        logging.info("kthxbai")
        server.shutdown()
        server.join(5.0)
        sys.exit(0)
