"""Run a local proxy server that distributes
   incoming requests to external proxies."""

import asyncio

import aiohttp

from proxybroker import Broker


async def fetch(url, proxy_url):
    resp = None
    try:
        async with aiohttp.ClientSession() as session, session.get(
            url, proxy=proxy_url
        ) as response:
            resp = await response.json()
    except (
        aiohttp.errors.ClientOSError,
        aiohttp.errors.ClientResponseError,
        aiohttp.errors.ServerDisconnectedError,
    ) as e:
        print('Error!\nURL: %s;\nError: %r' % (url, e))
    finally:
        return (url, resp)


async def get_pages(urls, proxy_url):
    tasks = [fetch(url, proxy_url) for url in urls]
    for task in asyncio.as_completed(tasks):
        url, content = await task
        print('%s\nDone!\nURL: %s;\nContent: %s' % ('-' * 20, url, content))


def main():
    host, port = '127.0.0.1', 8888  # by default

    loop = asyncio.get_event_loop()

    types = [('HTTP', 'High'), 'HTTPS', 'CONNECT:80']
    codes = [200, 301, 302]

    broker = Broker(max_tries=1, loop=loop)

    # Broker.serve() also supports all arguments that are accepted
    # Broker.find() method: data, countries, post, strict, dnsbl.
    broker.serve(
        host=host,
        port=port,
        types=types,
        limit=10,
        max_tries=3,
        prefer_connect=True,
        min_req_proxy=5,
        max_error_rate=0.5,
        max_resp_time=8,
        http_allowed_codes=codes,
        backlog=100,
    )

    urls = [
        'http://httpbin.org/get',
        'https://httpbin.org/get',
        'http://httpbin.org/redirect/1',
        'http://httpbin.org/status/404',
    ]

    proxy_url = 'http://%s:%d' % (host, port)
    loop.run_until_complete(get_pages(urls, proxy_url))

    broker.stop()


if __name__ == '__main__':
    main()
