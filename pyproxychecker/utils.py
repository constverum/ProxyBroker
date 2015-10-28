# import gzip
import asyncio
import os.path

import maxminddb

from .errors import *

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

mmdbSrc = os.path.join(BASE_DIR, 'data/GeoLite2-Country.mmdb')
mmdbReader = maxminddb.open_database(mmdbSrc)

MaxConcurrentConnections = asyncio.Semaphore(50)


def connector(ngtr_fn):
    async def wrapper(self, p):
        result = False
        attempt = 0
        while attempt < self.attemptsConnect:
            with (await MaxConcurrentConnections):
                attempt += 1

                # et = p.expected_type
                # firstCharNgtr = p.ngtr[0]
                # if et and attempt > 1 and et != firstCharNgtr:  # 'S' or 'H'
                #     result = False
                #     p.log('Expected another proxy type')
                #     break

                try:
                    await p.connect()
                except ProxyTimeoutError:
                    continue
                except ProxyConnError:
                    break
                result = await ngtr_fn(self, p)
                p.writer.close()
                p.log('Connection: closed')

                # if result is True:
                #     p.expected_type = firstCharNgtr
                #     p.log('Set expected proxy type: %s' % firstCharNgtr)

                if result is not None:  # True or False
                    break
        return result or False
    return wrapper
