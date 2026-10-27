"""Testes reais de transporte e política de repetição."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from client import Client
from core import expression
from server import Handler

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post(self, body):
        req = Request(self.url + '/rpc', data=body, headers={'Content-Type': 'application/json'})
        with urlopen(req) as response:
            body = response.read()
            return response.status, json.loads(body) if body else None

    def test_operations_and_modes(self):
        for protocol in ('rpc', 'rest'):
            client = Client(protocol, self.url)
            for method, expected in [('somar', 13), ('subtrair', 7), ('multiplicar', 30), ('dividir', 10/3)]:
                with self.subTest(protocol=protocol, method=method):
                    self.assertEqual(client.call(method, dict(a=10, b=3)), expected)
            for mode in ('cliente', 'servidor'):
                self.assertEqual(client.evaluate('(10 + 15) * 4', mode), 100)
                self.assertEqual(client.evaluate('-2 + 3 * (8 / 4)', mode), 4)
                with self.assertRaises(ValueError):
                    client.evaluate('1/0', mode)

    def test_decomposition(self):
        calls = []
        def invoke(method, params):
            calls.append((method, params))
            return 25 if method == 'somar' else 100
        self.assertEqual(expression('(10+15)*4', invoke), 100)
        self.assertEqual([m for m, p in calls], ['somar', 'multiplicar'])
        calls.clear()
        with self.assertRaises(ValueError):
            expression('(1+2)+__import__("os")', invoke)
        self.assertEqual(calls, [])

    def test_rpc_contract(self):
        self.assertEqual(self.post(b'{')[1]['error']['code'], -32700)
        for payload, code in [([], -32600), ({}, -32600), (dict(jsonrpc='2.0', id=3, method='x'), -32601), (dict(jsonrpc='2.0', id=4, method='somar', params=[1]), -32602)]:
            self.assertEqual(self.post(json.dumps(payload).encode())[1]['error']['code'], code)
        notification = dict(jsonrpc='2.0', method='somar', params=[1, 2])
        self.assertEqual(self.post(json.dumps(notification).encode()), (204, None))
        batch = [notification, dict(notification, id=5)]
        self.assertEqual(self.post(json.dumps(batch).encode())[1], [dict(jsonrpc='2.0', id=5, result=3)])

    def test_invalid_expressions(self):
        for protocol in ('rpc', 'rest'):
            client = Client(protocol, self.url)
            for text in ['True+1', '2**3', '1//2', 'x+1', '1+', '1e999', '']:
                for mode in ('cliente', 'servidor'):
                    with self.subTest(text=text, mode=mode, protocol=protocol), self.assertRaises(ValueError):
                        client.evaluate(text, mode)

    def test_retry_over_http(self):
        class Flaky(BaseHTTPRequestHandler):
            count = 0
            status = 503
            recover = True
            def log_message(self, *args):
                pass
            def do_POST(self):
                type(self).count += 1
                self.rfile.read(int(self.headers['Content-Length']))
                status = 200 if self.recover and self.count >= 3 else self.status
                body = b'{"result": 3}' if status == 200 else b'{"error": "simulated"}'
                self.send_response(status)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Flaky)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        waits = []
        client = Client('rest', f'http://127.0.0.1:{server.server_port}', sleep=waits.append)
        try:
            self.assertEqual(client.call('somar', dict(a=1, b=2)), 3)
            self.assertEqual(Flaky.count, 3)
            self.assertTrue(0.5 <= waits[0] <= 0.6 and 1 <= waits[1] <= 1.1)
            for status, attempts in [(422, 1), (503, 4), (429, 4)]:
                Flaky.count, Flaky.status, Flaky.recover = 0, status, False
                waits.clear()
                with self.assertRaises(ValueError):
                    client.call('somar', dict(a=1, b=2))
                self.assertEqual(Flaky.count, attempts)
                self.assertEqual(len(waits), attempts - 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

if __name__ == '__main__':
    unittest.main(verbosity=2)

