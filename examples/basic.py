"""Find and show 10 working HTTP(S) proxies."""

import asyncio

from proxybroker import Broker


async def show(proxies):
    while True:
        proxy = await proxies.get()
        if proxy is None:
            break
        print('Found proxy: %s' % proxy)


proxies = asyncio.Queue()
broker = Broker(proxies)
tasks = asyncio.gather(broker.find(types=['HTTP', 'HTTPS'], limit=10), show(proxies))

loop = asyncio.get_event_loop()
loop.run_until_complete(tasks)
