import asyncio
# import aiohttp
import unittest
from unittest.mock import Mock, MagicMock, patch

from proxybroker import Broker, Proxy
from proxybroker.utils import *


# def _fake_coroutine(self, mock, return_value):
#     def coro(*args, **kw):
#         if isinstance(return_value, Exception):
#             raise return_value
#         return return_value
#         yield
#     mock.side_effect = coro


class AutoDecorateAsyncMeta(type):
    def __init__(self, classname, parents, namespace):
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

        for k, v in namespace.items():
            if k.startswith('test_') and asyncio.iscoroutinefunction(v):
                setattr(self, k, _run(v))
        return type.__init__(self, classname, parents, namespace)


class AsyncTestCase(unittest.TestCase, metaclass=AutoDecorateAsyncMeta):
    pass


class TestUtils(AsyncTestCase):
    def test_get_ip_info(self):
        self.assertEqual(get_ip_info('8.8.8.8'), ('US', 'United States'))
        self.assertEqual(get_ip_info('127.0.0.1'), ('--', 'Unknown'))

    def test_host_is_ip(self):
        self.assertTrue(host_is_ip('127.0.0.1'))
        self.assertFalse(host_is_ip('256.0.0.1'))

    def test_get_all_ip(self):
        page = "abc127.0.0.1:80abc127.0.0.1xx127.0.0.2:8080h"
        self.assertEqual(get_all_ip(page), {'127.0.0.1', '127.0.0.2'})

    async def test_set_my_ip(self):
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
            await set_my_ip(timeout=0.1)

        self.assertEqual(get_my_ip(), '127.0.0.1')


class TestProxy(AsyncTestCase):
    def setUp(self):
        Proxy._sem = asyncio.Semaphore(1)
        Proxy._timeout = 0.1

    def tearDown(self):
        pass

    async def test_create(self):
        self.assertIsInstance(await Proxy.create('127.0.0.1', '80'), Proxy)
        self.assertFalse(await Proxy.create('127.0.0.1', '65536'))
        self.assertFalse(await Proxy.create('256.0.0.1', '80'))

    async def test_repr(self):
        p = await Proxy.create('8.8.8.8', '80')
        p.avgRespTime = '1.12s'
        p.types = {'HTTP': 'Anonymous', 'HTTPS': None}
        self.assertEqual(repr(p), '<Proxy US 1.12s [HTTP: Anonymous, HTTPS] 8.8.8.8:80>')

        p.types = {'SOCKS4': None, 'SOCKS5': None}
        self.assertEqual(repr(p), '<Proxy US 1.12s [SOCKS4, SOCKS5] 8.8.8.8:80>')

        p = await Proxy.create('127.0.0.1', '80')
        p.avgRespTime = ''
        p.types = {'HTTPS': None, 'SOCKS5': None}
        self.assertEqual(repr(p), '<Proxy --  [HTTPS, SOCKS5] 127.0.0.1:80>')


if __name__ == '__main__':
    unittest.main()
