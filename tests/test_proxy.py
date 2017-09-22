import unittest
from unittest.mock import Mock, patch

from .utils import AsyncTestCase, ResolveResult, future_iter

import time
from asyncio.streams import StreamReader

from proxybroker import Proxy
from proxybroker.utils import log
from proxybroker.errors import ProxyConnError, ProxyTimeoutError
from proxybroker.resolver import Resolver
from proxybroker.negotiators import HttpsNgtr


class TestProxy(AsyncTestCase):
    def setUp(self):
        self.proxy = Proxy('127.0.0.1', '80', timeout=0.1)
        self.proxy._reader['conn'] = StreamReader()

    def tearDown(self):
        pass

    async def test_create_with_ip(self):
        self.assertIsInstance(await Proxy.create('127.0.0.1', '80'), Proxy)
        self.assertTrue(Proxy('127.0.0.1', '80'))

        with self.assertRaises(ValueError):
            await Proxy.create('127.0.0.1', '65536')
            await Proxy.create('256.0.0.1', '80')
        self.assertRaises(ValueError, Proxy, '256.0.0.1', '80')
        self.assertRaises(ValueError, Proxy, '127.0.0.1', '65536')

    async def test_create_with_domain(self):
        with patch("aiodns.DNSResolver.query") as query:
            query.side_effect = future_iter([ResolveResult('127.0.0.1', 0)])
            resolver = Resolver()
            proxy = await Proxy.create('testhost.com', '80', resolver=resolver)
            self.assertEqual(proxy.host, '127.0.0.1')

    def test_repr(self):
        p = Proxy('8.8.8.8', '80')
        p._runtimes = [1, 3, 2]
        p.types.update({'HTTP': 'Anonymous', 'HTTPS': None})
        self.assertEqual(repr(p), '<Proxy US 2.00s [HTTP: Anonymous, HTTPS] 8.8.8.8:80>')

        p.types.clear()
        p.types.update({'SOCKS4': None, 'SOCKS5': None})
        self.assertEqual(repr(p), '<Proxy US 2.00s [SOCKS4, SOCKS5] 8.8.8.8:80>')

        p = Proxy('127.0.0.1', '80')
        self.assertEqual(repr(p), '<Proxy -- 0.00s [] 127.0.0.1:80>')

    def test_as_json(self):
        p = Proxy('8.8.8.8', '3128')
        p._runtimes = [1, 3, 3]
        p.types.update({'HTTP': 'Anonymous', 'HTTPS': None})
        json_tpl = {
            'host': '8.8.8.8',
            'port': 3128,
            'geo': {
                'country': {
                    'code': 'US',
                    'name': 'United States'
                }
            },
            'types': [
                {'type': 'HTTP', 'level': 'Anonymous'},
                {'type': 'HTTPS', 'level': ''},
            ],
            'avg_resp_time': 2.33,
            'error_rate': 0,
        }
        self.assertEqual(p.as_json(), json_tpl)

        p = Proxy('127.0.0.1', '80')
        msg = 'MSG'
        stime = time.time()
        err = ProxyConnError
        p.log(msg, stime, err)
        p.stat['requests'] += 4

        json_tpl = {
            'host': '127.0.0.1',
            'port': 80,
            'geo': {
                'country': {
                    'code': '--',
                    'name': 'Unknown'
                }
            },
            'types': [],
            'avg_resp_time': 0,
            'error_rate': 0.25,
        }
        self.assertEqual(p.as_json(), json_tpl)

    def test_schemes(self):
        p = Proxy('127.0.0.1', '80')
        p.types.update({'HTTP': 'Anonymous', 'HTTPS': None})
        self.assertEqual(p.schemes, ('HTTP', 'HTTPS'))

        p = Proxy('127.0.0.1', '80')
        p.types['HTTPS'] = None
        self.assertEqual(p.schemes, ('HTTPS',))

        p = Proxy('127.0.0.1', '80')
        p.types.update({'SOCKS4': None, 'SOCKS5': None})
        self.assertEqual(p.schemes, ('HTTP', 'HTTPS'))

    def test_avg_resp_time(self):
        p = Proxy('127.0.0.1', '80')
        self.assertEqual(p.avg_resp_time, 0.0)
        p._runtimes = [1, 3, 2]
        self.assertEqual(p.avg_resp_time, 2.0)

    def test_geo(self):
        p = Proxy('127.0.0.1', '80')
        self.assertEqual(p.geo.code, '--')
        self.assertEqual(p.geo.name, 'Unknown')

        p = Proxy('8.8.8.8', '80')
        self.assertEqual(p.geo.code, 'US')
        self.assertEqual(p.geo.name, 'United States')

    def test_ngtr(self):
        p = Proxy('127.0.0.1', '80')
        p.ngtr = 'HTTPS'
        self.assertIsInstance(p.ngtr, HttpsNgtr)
        self.assertIs(p.ngtr._proxy, p)

    def test_log(self):
        p = Proxy('127.0.0.1', '80')
        msg = 'MSG'
        stime = time.time()
        err = ProxyConnError

        self.assertEqual(p.get_log(), [])
        self.assertEqual(p._runtimes, [])

        with self.assertLogs(log.name, level='DEBUG') as cm:
            p.log(msg)
            p.ngtr = 'HTTP'
            p.log(msg)
            self.assertIn(('INFO', msg, 0), p.get_log())
            self.assertIn(('HTTP', msg, 0), p.get_log())
            self.assertEqual(len(p.stat['errors']), 0)
            self.assertEqual(p._runtimes, [])
            self.assertEqual(
                cm.output,
                ['DEBUG:proxybroker:127.0.0.1:80 [INFO]: MSG; Runtime: 0.00',
                 'DEBUG:proxybroker:127.0.0.1:80 [HTTP]: MSG; Runtime: 0.00'])

        p.log(msg, stime, err)
        p.log(msg, stime, err)
        self.assertEqual(len(p.stat['errors']), 1)
        self.assertEqual(sum(p.stat['errors'].values()), 2)
        self.assertEqual(p.stat['errors'][err.errmsg], 2)
        self.assertAlmostEqual(p._runtimes[-1], 0.0, places=1)

        len_runtimes = len(p._runtimes)
        p.log(msg + 'timeout', stime)
        self.assertEqual(len(p._runtimes), len_runtimes)

        msg = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do'
        p.log(msg)
        last_msg = p.get_log()[-1][1]
        cropped = msg[:60] + '...'
        self.assertEqual(last_msg, cropped)

    async def test_recv(self):
        resp = b'HTTP/1.1 200 OK\r\nContent-Length: 7\r\n\r\nabcdef\n'
        self.proxy.reader.feed_data(resp)
        self.assertEqual(await self.proxy.recv(), resp)

    async def test_recv_eof(self):
        resp = b'HTTP/1.1 200 OK\r\n\r\nabcdef'
        self.proxy.reader.feed_data(resp)
        self.proxy.reader.feed_eof()
        self.assertEqual(await self.proxy.recv(), resp)

    async def test_recv_length(self):
        self.proxy.reader.feed_data(b'abc')
        self.assertEqual(await self.proxy.recv(length=3), b'abc')
        self.proxy.reader._buffer.clear()

        self.proxy.reader.feed_data(b'abcdef')
        self.assertEqual(await self.proxy.recv(length=3), b'abc')
        self.proxy.reader._buffer.clear()

        # FIXME: Without override `proxy` will be raised
        # RuntimeError: Event loop is closed.
        self.setUp()
        self.proxy.reader.feed_data(b'ab')
        with self.assertRaises(ProxyTimeoutError):
            await self.proxy.recv(length=3)

    async def test_recv_head_only(self):
        self.proxy.reader.feed_data(b'HTTP/1.1 200 Connection established\r\n\r\n')
        self.assertEqual(await self.proxy.recv(head_only=True),
                         b'HTTP/1.1 200 Connection established\r\n\r\n')
        self.proxy.reader._buffer.clear()

        self.proxy.reader.feed_data(b'HTTP/1.1 200 OK\r\nServer: 0\r\n\r\nabcd')
        self.assertEqual(await self.proxy.recv(head_only=True),
                         b'HTTP/1.1 200 OK\r\nServer: 0\r\n\r\n')
        self.proxy.reader._buffer.clear()

        # FIXME: Without override `proxy` will be raised
        # RuntimeError: Event loop is closed.
        self.setUp()
        self.proxy.reader.feed_data(b'<html>abc</html>')
        with self.assertRaises(ProxyTimeoutError):
            await self.proxy.recv(head_only=True)

    async def test_recv_content_length(self):
        resp = b'HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\n{a}\n'
        self.proxy.reader.feed_data(resp)
        self.assertEqual(await self.proxy.recv(), resp)

    async def test_recv_content_encoding(self):
        resp = (b'HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\n'
                b'Content-Length: 7\r\n\r\n\x1f\x8b\x08\x00\n\x00\x00')
        self.proxy.reader.feed_data(resp)
        self.proxy.reader.feed_eof()
        self.assertEqual(await self.proxy.recv(), resp)

    async def test_recv_content_encoding_without_eof(self):
        # FIXME: Without override `proxy` will be raised
        # RuntimeError: Event loop is closed.
        self.setUp()
        resp = (b'HTTP/1.1 200 OK\r\n'
                b'Content-Encoding: gzip\r\n'
                b'Content-Length: 7\r\n\r\n'
                b'\x1f\x8b\x08\x00\n\x00\x00')
        self.proxy.reader.feed_data(resp)
        with self.assertRaises(ProxyTimeoutError):
            await self.proxy.recv()

    async def test_recv_content_encoding_chunked(self):
        resp = (b'HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\n'
                b'Transfer-Encoding: chunked\r\n\r\n3\x1f\x8b\x00\r\n0\r\n')
        self.proxy.reader.feed_data(resp)
        self.assertEqual(await self.proxy.recv(), resp)
        self.proxy.reader._buffer.clear()

        resp = (b'HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\n'
                b'Transfer-Encoding: chunked\r\n\r\n'
                b'5a' + b'\x1f' * 90 + b'\r\n\r\n0\r\n')
        self.proxy.reader.feed_data(resp)
        self.assertEqual(await self.proxy.recv(), resp)
