import asyncio
# import aiohttp
import unittest
from unittest.mock import Mock, MagicMock, patch

from proxybroker import Broker
from proxybroker.utils import *


def asynctest(f):
    def inner(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(f(self))
        finally:
            loop.close()
    return inner


class AutoDecorateAsyncMetaclass(type):
    def __init__(self, classname, parents, namespace):
        for k, v in namespace.items():
            if k.startswith('test_') and asyncio.iscoroutinefunction(v):
                setattr(self, k, asynctest(v))
        return type.__init__(self, classname, parents, namespace)


class AsyncTestCase(unittest.TestCase, metaclass=AutoDecorateAsyncMetaclass):
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

        with patch("aiohttp.client.ClientSession._request") as patched:
            patched.side_effect = side_effect
            await set_my_ip(timeout=0.1)

        self.assertEqual(get_my_ip(), '127.0.0.1')


if __name__ == '__main__':
    unittest.main()
