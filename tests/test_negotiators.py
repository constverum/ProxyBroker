import unittest
from unittest.mock import patch, call

from .utils import AsyncTestCase, future_iter

from proxybroker import Proxy
from proxybroker.errors import *
from proxybroker.resolver import Resolver
from proxybroker.negotiators import _CONNECT_request


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
            b'HTTP/1.1 200 Connection established\r\n\r\n',
            b'220 smtp2.test.com')
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

    async def test_negotiate_err_bad_resp_3(self):
        self.send.side_effect = future_iter(None)
        self.recv.side_effect = future_iter(
            b'HTTP/1.1 200 OK\r\n\r\n', b'')

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
