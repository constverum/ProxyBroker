import asyncio
from collections import namedtuple

ResolveResult = namedtuple('ResolveResult', ['host', 'ttl'])


def future_iter(*args):
    for resp in args:
        f = asyncio.Future()
        f.set_result(resp)
        yield f
