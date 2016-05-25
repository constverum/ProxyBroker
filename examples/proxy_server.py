"""Run a local proxy server that distributes requests to external proxies."""

import asyncio
import aiohttp
import logging
from proxybroker import Broker


def start_server(host, port, loop):
    # Types (protocols) that need to be checked for the proxy support
    # and level of anonymity (it makes sense to specify for HTTP only).
    types = [('HTTP', 'High'), 'HTTPS', 'CONNECT:80']

    # Limit in serve() mode works slightly differently than find().
    # When the Broker will find a specified number of working proxies,
    # new proxies check will be paused (not stopped as in find()!).
    # The resumption of checking will begin only if found proxies will be
    # discarded in the process of working with them
    # (see `max_error_rate`, `max_resp_time`).
    # The check will run until it finds one working proxy and paused again
    limit = 100  # by default

    # Limit the maximum number attempts of check proxy
    # And in serve mode: the number of attempts to process a request.
    # Attempts can be made with different proxies
    max_tries = 3  # by default

    # Minimum number of processed requests to decide
    # whether to use it further or reject.
    min_req_proxy = 5  # by default

    # Maximum percentage of requests that ended with an error.
    # By example: 0.5 = 50%
    max_error_rate = 0.5  # by default

    # Maximum response time. If proxy.avg_resp_time
    # exceeds this value, proxy will be rejected. In seconds.
    max_resp_time = 8  # by default

    # Flag that indicates whether to use the CONNECT method if possible.
    # Makes sense if among these types of `CONNECT:80`.
    # If it's True and a proxy supports HTTP(GET or POST), and CONNECT method,
    # then preference will be given to the CONNECT method
    prefer_connect = True  # False by default

    # Acceptable HTTP codes returned by proxy on requests.
    # If the proxy return code, not included in this list, it will be
    # considered as a proxy error, not a wrong/unavailable address.
    # For example, if the proxy will return a 404 Not Found response -
    # this will be considered as an error of a proxy.
    # Checks only for HTTP protocol, HTTPS not supported at the moment.
    # By default the list is empty and the response code is not verified.
    http_allowed_codes = [200, 301, 302]

    # Maximum number of queued connections passed to listen
    backlog = 100  # by default

    # Also supports all arguments that are accepted Broker.find() method.
    # By example: data, countries, post, strict, dnsbl.
    broker = Broker(max_tries=max_tries, loop=loop)
    broker.serve(
        host=host, port=port, types=types, limit=limit,
        prefer_connect=prefer_connect, min_req_proxy=min_req_proxy,
        max_error_rate=max_error_rate, max_resp_time=max_resp_time,
        http_allowed_codes=http_allowed_codes, backlog=backlog)
    return broker


def get_pages(host, port, urls, loop):
    print('fetch_pages: %s' % urls)
    tasks = asyncio.gather(*[fetch(host, port, url) for url in urls])
    pages = loop.run_until_complete(tasks)
    print('all pages fetched!')
    return pages


async def fetch(host, port, url):
    logger.info('url: %s; try fetch' % (url,))
    conn = aiohttp.ProxyConnector('http://%s:%d' % (host, port))
    resp = None
    try:
        with aiohttp.ClientSession(connector=conn) as session:
            async with session.get(url) as response:
                logger.info('url: %s; status: %d' % (url, response.status))
                resp = await response.read()
    except (aiohttp.errors.ClientOSError, aiohttp.errors.ClientResponseError,
            aiohttp.errors.ServerDisconnectedError) as e:
        logger.error('url: %s; error: %r' % (url, e))
    finally:
        return (url, resp)


def main():
    urls = ['http://httpbin.org/get', 'https://httpbin.org/get',
            'http://httpbin.org/redirect/1', 'http://httpbin.org/status/404']

    host, port = '127.0.0.1', 8888  # by default

    loop = asyncio.get_event_loop()

    broker = start_server(host, port, loop)
    pages = get_pages(host, port, urls, loop)

    for url, content in pages:
        print('url: %s; content: %.30s' % (url, content))

    broker.stop()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger('Parser')

    main()
