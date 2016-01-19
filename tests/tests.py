import asyncio
# import aiohttp
import unittest
from unittest.mock import Mock, MagicMock, patch

from proxybroker import Broker
from proxybroker.utils import *
from proxybroker.utils import REAL_IP

class TestUtils(unittest.TestCase):

    def test_get_ip_info(self):
        self.assertEqual(get_ip_info('8.8.8.8'), ('US', 'United States'))
        self.assertEqual(get_ip_info('127.0.0.1'), ('--', 'Unknown'))

    def test_host_is_ip(self):
        self.assertTrue(host_is_ip('127.0.0.1'))
        self.assertFalse(host_is_ip('256.0.0.1'))

    def test_get_all_ip(self):
        page = "abc127.0.0.1:80abc127.0.0.1xx127.0.0.2:8080h"
        self.assertEqual(get_all_ip(page), {'127.0.0.1', '127.0.0.2'})

    def test_set_my_ip(self):
        def side_effect(*args, **kwargs):
            def _side_effect(*args, **kwargs):
                fut = asyncio.Future(loop=loop)
                fut.set_result({'origin': '127.0.0.1'})
                return fut
            resp = Mock()
            resp.json.side_effect = resp.release.side_effect = _side_effect
            fut = asyncio.Future(loop=loop)
            fut.set_result(resp)
            return fut

        loop = asyncio.get_event_loop()
        with patch("aiohttp.client.ClientSession._request") as patched:
            patched.side_effect = side_effect
            loop.run_until_complete(set_my_ip(timeout=1, loop=loop))

        self.assertEqual(get_my_ip(), '127.0.0.1')





if __name__ == '__main__':
    unittest.main()
