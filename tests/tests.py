import time
import socket
import asyncio
import aiodns
import unittest
from unittest.mock import Mock, MagicMock, patch, call
from collections import namedtuple


from proxybroker.utils import *
from proxybroker import Broker, Proxy
from proxybroker.errors import *
from proxybroker.resolver import Resolver
from proxybroker.negotiators import _CONNECT_request, HttpsNgtr


# def _fake_coroutine(self, mock, return_value):
#     def coro(*args, **kw):
#         if isinstance(return_value, Exception):
#             raise return_value
#         return return_value
#         yield
#     mock.side_effect = coro


ResolveResult = namedtuple('ResolveResult', ['host', 'ttl'])


def future_iter(*args):
    for resp in args:
        f = asyncio.Future()
        f.set_result(resp)
        yield f


class AutoDecorateAsyncMeta(type):
    def __init__(self, name, bases, _dict):
        def _run(func):
            def inner(*args, **kwargs):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(func(*args, **kwargs))
                finally:
                    loop.stop()
                    loop.close()
            return inner

        for k, v in _dict.items():
            if k.startswith('test_') and asyncio.iscoroutinefunction(v):
                setattr(self, k, _run(v))
        return type.__init__(self, name, bases, _dict)


class AsyncTestCase(unittest.TestCase, metaclass=AutoDecorateAsyncMeta):
    pass


class TestUtils(AsyncTestCase):
    def test_get_all_ip(self):
        page = "abc127.0.0.1:80abc127.0.0.1xx127.0.0.2:8080h"
        self.assertEqual(get_all_ip(page), {'127.0.0.1', '127.0.0.2'})

    def test_get_status_code(self):
        self.assertEqual(get_status_code('HTTP/1.1 200 OK\r\n'), 200)
        self.assertEqual(get_status_code('<html>123</html>\r\n'), 400)
        self.assertEqual(get_status_code(b'HTTP/1.1 403 Forbidden\r\n'), 403)
        self.assertEqual(get_status_code(b'HTTP/1.1 400 Bad Request\r\n'), 400)

    def test_parse_status_line(self):
        self.assertEqual(parse_status_line('HTTP/1.1 200 OK'),
                         {'Version': 'HTTP/1.1', 'Status': 200, 'Reason': 'OK'})
        self.assertEqual(parse_status_line('HTTP/1.1 404 NOT FOUND'),
                         {'Version': 'HTTP/1.1', 'Status': 404, 'Reason': 'Not Found'})
        self.assertEqual(parse_status_line('GET / HTTP/1.1'),
                         {'Version': 'HTTP/1.1', 'Method': 'GET', 'Path': '/'})
        self.assertRaises(BadStatusLine, parse_status_line, '<!DOCTYPE html ')

    def test_parse_headers(self):
        req = (b'GET /go HTTP/1.1\r\nContent-Length: 0\r\nAccept-Encoding: '
               b'gzip, deflate\r\nHost: host.com\r\nConnection: close\r\n\r\n')
        hdrs = {'Method': 'GET', 'Version': 'HTTP/1.1', 'Path': '/go',
                'Content-Length': '0', 'Host': 'host.com', 'Connection': 'close',
                'Accept-Encoding': 'gzip, deflate'}
        self.assertEqual(parse_headers(req), hdrs)
        resp = (b'HTTP/1.1 200 OK\r\nContent-Length: 1133\r\nConnection: close'
                b'\r\nContent-Type: text/html; charset=UTF-8\r\n\r\n')
        hdrs = {'Version': 'HTTP/1.1', 'Status': 200, 'Reason': 'OK',
                'Content-Length': '1133', 'Connection': 'close',
                'Content-Type': 'text/html; charset=UTF-8'}
        self.assertEqual(parse_headers(resp), hdrs)


class TestProxy(AsyncTestCase):
    def setUp(self):
        pass

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

    def test_schemes(self):
        p = Proxy('127.0.0.1', '80')
        p.types.update({'HTTP': 'Anonymous', 'HTTPS': None})
        # p.types['HTTP'], p.types['HTTPS'] = 'Anonymous', None
        self.assertEqual(p.schemes, ('HTTP', 'HTTPS'))

        p = Proxy('127.0.0.1', '80')
        p.types['HTTPS'] = None
        self.assertEqual(p.schemes, ('HTTPS',))

        p = Proxy('127.0.0.1', '80')
        p.types.update({'SOCKS4': None, 'SOCKS5': None})
        self.assertEqual(p.schemes, ('HTTP', 'HTTPS'))

    def test_avg_resp_time(self):
        p = Proxy('127.0.0.1', '80')
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


class TestResolver(AsyncTestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_host_is_ip(self):
        rs = Resolver(timeout=0.1)
        self.assertTrue(rs.host_is_ip('127.0.0.1'))
        self.assertFalse(rs.host_is_ip('256.0.0.1'))
        self.assertFalse(rs.host_is_ip('test.com'))

    def test_get_ip_info(self):
        rs = Resolver(timeout=0.1)
        self.assertEqual(rs.get_ip_info('test.com'), ('--', 'Unknown'))
        self.assertEqual(rs.get_ip_info('127.0.0.1'), ('--', 'Unknown'))
        self.assertEqual(rs.get_ip_info('8.8.8.8'), ('US', 'United States'))

    async def test_get_real_ext_ip(self):
        rs = Resolver(timeout=0.1)

        def side_effect(*args, **kwargs):
            def _side_effect(*args, **kwargs):
                fut = asyncio.Future()
                fut.set_result({'origin': '127.0.0.1'})
                return fut
            resp = Mock()
            resp.json.side_effect = resp.release.side_effect = _side_effect
            fut = asyncio.Future()
            fut.set_result(resp)
            return fut

        with patch("aiohttp.client.ClientSession._request") as resp:
            resp.side_effect = side_effect
            self.assertEqual(await rs.get_real_ext_ip(), '127.0.0.1')

    async def test_resolve(self):
        rs = Resolver(timeout=0.1)
        self.assertEqual(await rs.resolve('127.0.0.1'), '127.0.0.1')

        with self.assertRaises(ResolveError):
            await rs.resolve('256.0.0.1')

        with patch("aiodns.DNSResolver.query") as query:
            query.side_effect = future_iter([ResolveResult('127.0.0.1', 0)])
            self.assertEqual(await rs.resolve('test.com'), '127.0.0.1')

    async def test_resolve_family(self):
        rs = Resolver(timeout=0.1)
        with patch("aiodns.DNSResolver.query") as query:
            query.side_effect = future_iter([ResolveResult('127.0.0.2', 0)])
            resp = [{'hostname': 'test2.com', 'host': '127.0.0.2', 'port': 80,
                     'family': socket.AF_INET, 'proto': socket.IPPROTO_IP,
                     'flags': socket.AI_NUMERICHOST}]
            self.assertEqual(
                await rs.resolve('test2.com', family=socket.AF_INET), resp)

    async def test_resolve_cache(self):
        rs = Resolver(timeout=0.1)

        with patch("aiodns.DNSResolver.query") as query:
            query.side_effect = future_iter([ResolveResult('127.0.0.1', 0)])
            await rs.resolve('test.com')

            query.side_effect = future_iter([ResolveResult('127.0.0.2', 0)])
            port = 80
            resp = [{'hostname': 'test2.com', 'host': '127.0.0.2', 'port': port,
                     'family': socket.AF_INET, 'proto': socket.IPPROTO_IP,
                     'flags': socket.AI_NUMERICHOST}]
            await rs.resolve('test2.com', port=80, family=socket.AF_INET)

        rs._resolve = None
        self.assertEqual(await rs.resolve('test.com'), '127.0.0.1')
        resp = await rs.resolve('test2.com')
        self.assertEqual(resp[0]['host'], '127.0.0.2')


class TestSocks5Ngtr(AsyncTestCase):
    def setUp(self):
        self.proxy = Proxy('127.0.0.1', '80')
        self.proxy.ngtr = 'SOCKS5'  # Socks5Ngtr()
        self._send = patch.object(Proxy, 'send')
        self._recv = patch.object(Proxy, 'recv')
        self.send = self._send.start()
        self.recv = self._recv.start()

    def tearDown(self):
        self._send.stop()
        self._recv.stop()

    def test_base_attrs(self):
        self.assertEqual(self.proxy.ngtr.name, 'SOCKS5')
        self.assertFalse(self.proxy.ngtr.check_anon_lvl)
        self.assertFalse(self.proxy.ngtr.use_full_path)

    async def test_negotiate(self):
        self.send.side_effect = future_iter(None, None)
        self.recv.side_effect = future_iter(
            b'\x05\x00', b'\x05\x00\x00\x01\xc0\xa8\x00\x18\xce\xdf')

        await self.proxy.ngtr.negotiate(ip='127.0.0.1')

        self.send.assert_has_calls([
            call(b'\x05\x01\x00'),
            call(b'\x05\x01\x00\x01\x7f\x00\x00\x01\x00P')])

    async def test_negotiate_custom_port(self):
        self.send.side_effect = future_iter(None, None)
        self.recv.side_effect = future_iter(b'\x05\x00', b'\x05\x00')

        await self.proxy.ngtr.negotiate(ip='127.0.0.1', port=443)

        self.send.assert_has_calls([
            call(b'\x05\x01\x00'),
            call(b'\x05\x01\x00\x01\x7f\x00\x00\x01\x01\xbb')])

    async def test_negotiate_err_bad_resp(self):
        self.send.side_effect = future_iter(None, None)
        self.recv.side_effect = future_iter(b'\x05\xff')

        with self.assertRaises(BadResponseError):
            await self.proxy.ngtr.negotiate(ip='127.0.0.1')

        self.send.assert_has_calls([call(b'\x05\x01\x00')])

    async def test_negotiate_err_fail_conn(self):
        self.send.side_effect = future_iter(None, None)
        self.recv.side_effect = future_iter(b'\x05\x00', b'\x05\x05')

        with self.assertRaises(BadResponseError):
            await self.proxy.ngtr.negotiate(ip='127.0.0.1')

        self.send.assert_has_calls([
            call(b'\x05\x01\x00'),
            call(b'\x05\x01\x00\x01\x7f\x00\x00\x01\x00P')])


class TestSocks4Ngtr(AsyncTestCase):
    def setUp(self):
        self.proxy = Proxy('127.0.0.1', '80')
        self.proxy.ngtr = 'SOCKS4'  # Socks4Ngtr()
        self._send = patch.object(Proxy, 'send')
        self._recv = patch.object(Proxy, 'recv')
        self.send = self._send.start()
        self.recv = self._recv.start()

    def tearDown(self):
        self._send.stop()
        self._recv.stop()

    def test_base_attrs(self):
        self.assertEqual(self.proxy.ngtr.name, 'SOCKS4')
        self.assertFalse(self.proxy.ngtr.check_anon_lvl)
        self.assertFalse(self.proxy.ngtr.use_full_path)

    async def test_negotiate(self):
        self.send.side_effect = future_iter(None, None)
        self.recv.side_effect = future_iter(b'\x00Z\x00\x00\x00\x00\x00\x00')

        await self.proxy.ngtr.negotiate(ip='127.0.0.1')

        self.send.assert_has_calls([
            call(b'\x04\x01\x00P\x7f\x00\x00\x01\x00')])

    async def test_negotiate_custom_port(self):
        self.send.side_effect = future_iter(None, None)
        self.recv.side_effect = future_iter(b'\x00Z\x00\x00\x00\x00\x00\x00')

        await self.proxy.ngtr.negotiate(ip='127.0.0.1', port=443)

        self.send.assert_has_calls([
            call(b'\x04\x01\x01\xbb\x7f\x00\x00\x01\x00')])

    async def test_negotiate_err_bad_resp(self):
        self.send.side_effect = future_iter(None, None)
        self.recv.side_effect = future_iter(b'HTTP/1.1 400 Bad Request')

        with self.assertRaises(BadResponseError):
            await self.proxy.ngtr.negotiate(ip='127.0.0.1')

    async def test_negotiate_err_fail_conn(self):
        self.send.side_effect = future_iter(None, None)
        self.recv.side_effect = future_iter(b'\x00[')  # 0x00, 0x5b

        with self.assertRaises(BadResponseError):
            await self.proxy.ngtr.negotiate(ip='127.0.0.1')


class TestConnect80Ngtr(AsyncTestCase):
    def setUp(self):
        self.proxy = Proxy('127.0.0.1', '80')
        self.proxy.ngtr = 'CONNECT:80'  # Connect80Ngtr()
        self._send = patch.object(Proxy, 'send')
        self._recv = patch.object(Proxy, 'recv')
        self.send = self._send.start()
        self.recv = self._recv.start()

    def tearDown(self):
        self._send.stop()
        self._recv.stop()

    def test_base_attrs(self):
        self.assertEqual(self.proxy.ngtr.name, 'CONNECT:80')
        self.assertFalse(self.proxy.ngtr.check_anon_lvl)
        self.assertFalse(self.proxy.ngtr.use_full_path)

    async def test_negotiate(self):
        self.send.side_effect = future_iter(None)
        self.recv.side_effect = future_iter(
            b'HTTP/1.1 200 Connection established\r\n\r\n')
        host = 'test.com'

        await self.proxy.ngtr.negotiate(host=host)

        req = _CONNECT_request(host=host, port=80)
        self.send.assert_has_calls([call(req)])

    async def test_negotiate_err_bad_resp(self):
        self.send.side_effect = future_iter(None)
        self.recv.side_effect = future_iter(
            b'HTTP/1.1 400 Bad Request\r\n\r\n')

        with self.assertRaises(BadStatusError):
            await self.proxy.ngtr.negotiate(host='test.com')

    async def test_negotiate_err_bad_resp_2(self):
        self.send.side_effect = future_iter(None)
        self.recv.side_effect = future_iter(
            b'<html>\r\n<head><title>400 Bad Request</title></head>\r\n')

        with self.assertRaises(BadStatusError):
            await self.proxy.ngtr.negotiate(host='test.com')


class TestConnect25Ngtr(AsyncTestCase):
    def setUp(self):
        self.proxy = Proxy('127.0.0.1', '80')
        self.proxy.ngtr = 'CONNECT:25'  # Connect25Ngtr()
        self._send = patch.object(Proxy, 'send')
        self._recv = patch.object(Proxy, 'recv')
        self.send = self._send.start()
        self.recv = self._recv.start()

    def tearDown(self):
        self._send.stop()
        self._recv.stop()

    def test_base_attrs(self):
        self.assertEqual(self.proxy.ngtr.name, 'CONNECT:25')
        self.assertFalse(self.proxy.ngtr.check_anon_lvl)
        self.assertFalse(self.proxy.ngtr.use_full_path)


    async def test_negotiate(self):
        self.send.side_effect = future_iter(None)
        self.recv.side_effect = future_iter(
            b'HTTP/1.1 200 Connection established\r\n\r\n')
        host = 'test.com'

        await self.proxy.ngtr.negotiate(host=host)

        req = _CONNECT_request(host=host, port=25)
        self.send.assert_has_calls([call(req)])

    async def test_negotiate_err_bad_resp(self):
        self.send.side_effect = future_iter(None)
        self.recv.side_effect = future_iter(
            b'HTTP/1.1 400 Bad Request\r\n\r\n')

        with self.assertRaises(BadStatusError):
            await self.proxy.ngtr.negotiate(host='test.com')

    async def test_negotiate_err_bad_resp_2(self):
        self.send.side_effect = future_iter(None)
        self.recv.side_effect = future_iter(
            b'<html>\r\n<head><title>400 Bad Request</title></head>\r\n')

        with self.assertRaises(BadStatusError):
            await self.proxy.ngtr.negotiate(host='test.com')


class TestHttpsNgtr(AsyncTestCase):
    def setUp(self):
        self.proxy = Proxy('127.0.0.1', '80')
        self.proxy.ngtr = 'HTTPS'  # HttpsNgtr()
        self._send = patch.object(Proxy, 'send')
        self._recv = patch.object(Proxy, 'recv')
        self._connect = patch.object(Proxy, 'connect')
        self.send = self._send.start()
        self.recv = self._recv.start()
        self.connect = self._connect.start()

    def tearDown(self):
        self._send.stop()
        self._recv.stop()
        self._connect.stop()

    def test_base_attrs(self):
        self.assertEqual(self.proxy.ngtr.name, 'HTTPS')
        self.assertFalse(self.proxy.ngtr.check_anon_lvl)
        self.assertFalse(self.proxy.ngtr.use_full_path)

    async def test_negotiate(self):
        self.send.side_effect = future_iter(None)
        self.recv.side_effect = future_iter(
            b'HTTP/1.1 200 Connection established\r\n\r\n')
        self.connect.side_effect = future_iter(None)
        host = 'test.com'

        await self.proxy.ngtr.negotiate(host=host)

        req = _CONNECT_request(host=host, port=443)
        self.send.assert_has_calls([call(req)])

    async def test_negotiate_err_bad_resp(self):
        self.send.side_effect = future_iter(None)
        self.recv.side_effect = future_iter(
            b'HTTP/1.1 400 Bad Request\r\n\r\n')
        self.connect.side_effect = future_iter(None)

        with self.assertRaises(BadStatusError):
            await self.proxy.ngtr.negotiate(host='test.com')

    async def test_negotiate_err_bad_resp_2(self):
        self.send.side_effect = future_iter(None)
        self.recv.side_effect = future_iter(
            b'<html>\r\n<head><title>400 Bad Request</title></head>\r\n')
        self.connect.side_effect = future_iter(None)

        with self.assertRaises(BadStatusError):
            await self.proxy.ngtr.negotiate(host='test.com')


class TestHttpNgtr(AsyncTestCase):
    def setUp(self):
        self.proxy = Proxy('127.0.0.1', '80')
        self.proxy.ngtr = 'HTTP'  # HttpNgtr()

    def test_base_attrs(self):
        self.assertEqual(self.proxy.ngtr.name, 'HTTP')
        self.assertTrue(self.proxy.ngtr.check_anon_lvl)
        self.assertTrue(self.proxy.ngtr.use_full_path)


if __name__ == '__main__':
    unittest.main()
