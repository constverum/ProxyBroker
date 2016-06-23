import unittest
from unittest.mock import Mock, patch

from .utils import AsyncTestCase, ResolveResult, future_iter

import socket
from asyncio import Future
from proxybroker.errors import ResolveError
from proxybroker.resolver import Resolver


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
                fut = Future()
                fut.set_result({'origin': '127.0.0.1'})
                return fut
            resp = Mock()
            resp.json.side_effect = resp.release.side_effect = _side_effect
            fut = Future()
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
