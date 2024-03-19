"""Run a local proxy server that distributes
   incoming requests to external proxies."""

import asyncio

import aiohttp


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

    # types = [('HTTP', 'High'), 'HTTPS', 'CONNECT:80']
    # codes = [200, 301, 302]

    urls = [
        'http://httpbin.org/get',
        'https://httpbin.org/get',
        'http://httpbin.org/redirect/1',
        'http://httpbin.org/status/404',
    ]

    proxy_url = 'http://%s:%d' % (host, port)
    loop.run_until_complete(get_pages(urls, proxy_url))


if __name__ == '__main__':
    main()
