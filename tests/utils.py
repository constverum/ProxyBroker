import asyncio
import unittest
from collections import namedtuple


class AutoDecorateAsyncMeta(type):
    def __init__(self, name, bases, _dict):
        def _run(func):
            def inner(*args, **kwargs):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(func(*args, **kwargs))
                finally:
                    loop.stop()
                    loop.close()
            return inner

        for k, v in _dict.items():
            if k.startswith('test_') and asyncio.iscoroutinefunction(v):
                setattr(self, k, _run(v))
        return type.__init__(self, name, bases, _dict)


class AsyncTestCase(unittest.TestCase, metaclass=AutoDecorateAsyncMeta):
    pass


ResolveResult = namedtuple('ResolveResult', ['host', 'ttl'])


def future_iter(*args):
    for resp in args:
        f = asyncio.Future()
        f.set_result(resp)
        yield f




# def _fake_coroutine(self, mock, return_value):
#     def coro(*args, **kw):
#         if isinstance(return_value, Exception):
#             raise return_value
#         return return_value
#         yield
#     mock.side_effect = coro
