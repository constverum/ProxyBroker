"""Find working proxies and use them concurrently.

Note: Pay attention to Broker.serve(), instead of the code listed below.
      Perhaps it will be much useful and friendlier.
"""

import asyncio
import logging
from functools import partial
from urllib.parse import urlparse

import aiohttp
import requests

from proxybroker import Broker, ProxyPool
from proxybroker.errors import NoProxyError


async def get_pages(urls, proxy_pool, timeout=10, loop=None):
    def _return_proxy_to_pool(proxy, f):
        proxy_pool.put(proxy)
    tasks = []
    for url in urls:
        try:
            proxy = await proxy_pool.get(
                scheme=urlparse(url).scheme.upper())
        except NoProxyError as e:
            logger.error('%s' % e)
            return
        proxy_url = 'http://%s:%d' % (proxy.host, proxy.port)
        task = asyncio.ensure_future(fetch_page_by_aiohttp(
            url, proxy_url, timeout, loop))
        # Or use `requests` with threads instead of asynchronous calls
        # task = loop.run_in_executor(None, partial(
        #     fetch_page_by_requests, url, proxy_url, timeout))
        task.add_done_callback(partial(_return_proxy_to_pool, proxy))
        tasks.append(task)

    for task in asyncio.as_completed(tasks):
        url, content = await task
        print('url: %s; content: %.30s' % (url, content))


def fetch_page_by_requests(url, proxy_url, timeout):
    resp = None
    proxies = {'http': proxy_url, 'https': proxy_url}
    try:
        response = requests.get(url, timeout=timeout, proxies=proxies)
        logger.debug('url: %s; status: %d' % (url, response.status_code))
        resp = response.content
    except (requests.exceptions.Timeout,) as e:
        logger.error('url: %s; error: %r' % (url, e))
    return (url, resp)


async def fetch_page_by_aiohttp(url, proxy_url, timeout, loop):
    resp = None
    try:
        with aiohttp.ClientSession(loop=loop) as session,\
             aiohttp.Timeout(timeout):
            async with session.get(url, proxy=proxy_url) as response:
                logger.info('url: %s; status: %d' % (url, response.status))
                resp = await response.read()
    except (aiohttp.errors.ClientOSError, aiohttp.errors.ClientResponseError,
            aiohttp.errors.ServerDisconnectedError, asyncio.TimeoutError) as e:
        logger.error('url: %s; error: %r' % (url, e))
    finally:
        return (url, resp)


def main():
    loop = asyncio.get_event_loop()

    proxies = asyncio.Queue(loop=loop)

    judges = ['http://httpbin.org/get?show_env',
              'https://httpbin.org/get?show_env']
    providers = ['http://www.proxylists.net/', 'http://fineproxy.org/eng/']

    broker = Broker(
        proxies, timeout=8, max_conn=200, max_tries=3, verify_ssl=False,
        judges=judges, providers=providers, loop=loop)

    types = [('HTTP', ('Anonymous', 'High')), 'HTTPS']
    countries = ['US', 'DE', 'FR']

    urls = ['http://httpbin.org/get', 'https://httpbin.org/get',
            'http://httpbin.org/redirect/1', 'http://httpbin.org/status/404']

    proxy_pool = ProxyPool(proxies)

    tasks = asyncio.gather(
        broker.find(types=types, countries=countries, post=False,
                    strict=True, limit=10),
        get_pages(urls, proxy_pool, loop=loop))
    loop.run_until_complete(tasks)

    broker.show_stats(verbose=True)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='[%H:%M:%S]', level=logging.INFO)
    logger = logging.getLogger('Parser')

    main()
