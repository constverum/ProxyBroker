"""Find working proxies and use them concurrently.

Note: Pay attention to Broker.serve(), instead of the code listed below.
      Perhaps it will be much useful and friendlier.
"""

import asyncio
from urllib.parse import urlparse

import aiohttp

from proxybroker import Broker, ProxyPool
from proxybroker.errors import NoProxyError


async def get_pages(urls, proxy_pool, timeout=10, loop=None):
    tasks = [fetch(url, proxy_pool, timeout, loop) for url in urls]
    for task in asyncio.as_completed(tasks):
        url, content = await task
        print('Done! url: %s; content: %.30s' % (url, content))


async def fetch(url, proxy_pool, timeout, loop):
    resp, proxy = None, None
    try:
        proxy = await proxy_pool.get(scheme=urlparse(url).scheme)
        proxy_url = 'http://%s:%d' % (proxy.host, proxy.port)
        with aiohttp.Timeout(timeout, loop=loop):
            async with aiohttp.ClientSession(loop=loop) as session:
                async with session.get(url, proxy=proxy_url) as response:
                    resp = await response.read()
    except (aiohttp.errors.ClientOSError, aiohttp.errors.ClientResponseError,
            aiohttp.errors.ServerDisconnectedError, asyncio.TimeoutError,
            NoProxyError) as e:
        print('Error. url: %s; error: %r', url, e)
    finally:
        if proxy:
            proxy_pool.put(proxy)
        return (url, resp)


def main():
    loop = asyncio.get_event_loop()

    proxies = asyncio.Queue(loop=loop)
    proxy_pool = ProxyPool(proxies)

    judges = ['http://httpbin.org/get?show_env',
              'https://httpbin.org/get?show_env']
    providers = ['http://www.proxylists.net/', 'http://fineproxy.org/eng/fresh-proxies/']

    broker = Broker(
        proxies, timeout=8, max_conn=200, max_tries=3, verify_ssl=False,
        judges=judges, providers=providers, loop=loop)

    types = [('HTTP', ('Anonymous', 'High')), ]
    countries = ['US', 'DE', 'FR']

    urls = ['http://httpbin.org/get', 'http://httpbin.org/redirect/1',
            'http://httpbin.org/anything', 'http://httpbin.org/status/404']

    tasks = asyncio.gather(
        broker.find(types=types, countries=countries, strict=True, limit=10),
        get_pages(urls, proxy_pool, loop=loop))
    loop.run_until_complete(tasks)

    # broker.show_stats(verbose=True)


if __name__ == '__main__':
    main()
