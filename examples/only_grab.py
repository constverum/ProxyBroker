"""Gather proxies from the providers without
   checking and save them to a file."""

import asyncio
import warnings
import logging

from proxybroker import Broker
from proxybroker.providers import Provider, Blogspot_com, Spys_ru, Proxylist_me


async def save(proxies, filename):
    """Save proxies to a file."""
    with open(filename, 'w') as f:
        while True:
            proxy = await proxies.get()
            if proxy is None:
                logging.info('got None from proxies queue')
                break
            for proto in proxy.types or ['http', 'https']:
                proto = proto.lower()
                row = '%s://%s:%d\n' % (proto, proxy.host, proxy.port)
                f.write(row)


def main():
    providers = [
        # Blogspot_com(proto=('HTTP', 'HTTPS')),  # noqa; 24800
        Provider(
            url='https://geekelectronics.org/my-servisy/proxy',
            proto=('HTTP', 'CONNECT:80', 'HTTPS', 'CONNECT:25'),
        ),  # 400
        Spys_ru(proto=('HTTP', 'CONNECT:80', 'HTTPS', 'CONNECT:25')),  # noqa; 660
    ]
    proxies = asyncio.Queue()
    broker = Broker(proxies)
    # broker = Broker(proxies, providers=providers)
    tasks = asyncio.gather(
        broker.grab(),
        save(proxies, filename='proxies.txt'),
    )
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.slow_callback_duration = 1
    # Report all mistakes managing asynchronous resources.
    warnings.simplefilter('always', ResourceWarning)
    loop.run_until_complete(tasks)


if __name__ == '__main__':
    logging.basicConfig(level='INFO')
    main()
