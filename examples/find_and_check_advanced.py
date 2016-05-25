"""Find working proxies and use them in parallel."""

import asyncio
import aiohttp
import logging
import requests
from functools import partial
from proxybroker import Broker


async def use(proxies, timeout=10, loop=None):
    tasks = []
    while True:
        proxy = await proxies.get()
        if proxy is None:
            break
        elif ('SOCKS4', 'SOCKS5') & proxy.types.keys():  # filter by type
            logger.info('Found SOCKS proxy: %s' % proxy)
        elif 'HTTPS' in proxy.types:
            task = asyncio.ensure_future(fetch_page_by_aiohttp(
                proxy, 'https://httpbin.org/get', timeout, loop))
            tasks.append(task)
        elif 'HTTP' in proxy.types:
            # Used threads instead of asynchronous calls
            task = loop.run_in_executor(None, partial(
                fetch_page_by_requests, proxy, 'http://httpbin.org/get', timeout))
            tasks.append(task)
        else:
            logger.info('It seems that only supports the'
                        'CONNECT method to port 80: %s' % proxy)

    for task in asyncio.as_completed(tasks):
        url, content = await task
        logger.info('url: %s; content: %.30s' % (url, content))


def fetch_page_by_requests(proxy, url, timeout):
    resp = None
    proxies = {'http': 'http://%s:%d' % (proxy.host, proxy.port),
               'https': 'http://%s:%d' % (proxy.host, proxy.port)}
    try:
        response = requests.get(url, timeout=timeout, proxies=proxies)
        logger.debu('url: %s; status: %d' % (url, response.status_code))
        resp = response.content
    except (requests.exceptions.Timeout,) as e:
        logger.error('url: %s; error: %r' % (url, e))
    return (url, resp)


async def fetch_page_by_aiohttp(proxy, url, timeout, loop):
    resp = None
    conn = aiohttp.ProxyConnector('http://%s:%d' % (proxy.host, proxy.port))
    try:
        with aiohttp.ClientSession(connector=conn, loop=loop) as session,\
             aiohttp.Timeout(timeout):
            async with session.get(url) as response:
                logger.info('url: %s; status: %d' % (url, response.status))
                resp = await response.read()
    except (aiohttp.errors.ClientOSError, aiohttp.errors.ClientResponseError,
            aiohttp.errors.ServerDisconnectedError, asyncio.TimeoutError) as e:
        logger.error('url: %s; error: %r' % (url, e))
    finally:
        return (url, resp)


def get_broker(proxies, loop=None):
    # Queue of checked proxies
    queue = proxies

    # The timeout of the request in seconds.
    timeout = 8  # by default

    # Limit for the maximum number of concurrent connections
    max_conn = 200  # by default

    # Limits for the maximum number of attempts to check a proxy.
    # And in serve mode: the number of attempts to process a request
    max_tries = 3  # by default

    # Check ssl certifications
    verify_ssl = False  # by default

    # Urls of pages that show HTTP headers and IP address
    judges = ['http://httpbin.org/get?show_env',
              'https://httpbin.org/get?show_env']

    # Urls of pages where to find proxies
    providers = ['http://www.proxylists.net/', 'http://fineproxy.org/eng/']

    return Broker(
        queue=queue, timeout=timeout, max_conn=max_conn, max_tries=max_tries,
        verify_ssl=verify_ssl, judges=judges, providers=providers, loop=loop)


async def find(broker):
    # Types (protocols) that need to be check on support by proxy.
    # and level of anonymity (it makes sense to specify for HTTP only).
    # For example: find proxies with only anonymous & high levels
    # of anonymity for http protocol and high for other
    types = [('HTTP', ('Anonymous', 'High')), 'HTTPS',
             'CONNECT:80', 'SOCKS4', 'SOCKS5']

    # Check proxy only from specified countries
    countries = ['US', 'GB', 'DE', 'FR']

    # Flag indicating use POST instead of GET for requests when checking proxies
    post = False  # by default

    # Flag indicating that anonymity levels of the types(protocols) supported
    # by the proxy must be equal to the required types and levels of anonymity.
    # If strict mode is enabled, the proxy will be
    # considered as passed the check only if all specified
    # types (protocols) match the specified anonymity levels.
    # If strict mode is off (by default), for a successful check
    # is enough to satisfy any one of the specified types.
    strict = False  # by default

    # Maximum number of working proxies
    limit = 3  # by default is not limited (!)

    # Grabs and checks found proxies
    await broker.find(types=types, countries=countries, post=post,
                      strict=strict, limit=limit)


def main():
    loop = asyncio.get_event_loop()

    proxies = asyncio.Queue(loop=loop)
    broker = get_broker(proxies, loop=loop)
    tasks = asyncio.gather(find(broker), use(proxies, timeout=10, loop=loop))
    loop.run_until_complete(tasks)

    # Show statistics of checking proxies. Used for debugging, but you may also
    # be interested? verbose - indicating whether to print verbose messages
    broker.show_stats(verbose=True)  # False by default


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='[%H:%M:%S]', level=logging.INFO)
    logger = logging.getLogger('Parser')

    main()
