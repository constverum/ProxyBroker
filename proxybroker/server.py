import asyncio
import heapq

from .errors import NoProxyError
from .interceptor import Interceptor
from .utils import log
from .resolver import Resolver


class ProxyPool:
    """Imports and gives proxies from queue on demand."""

    def __init__(
        self, proxies, min_req_proxy=5, max_error_rate=0.5, max_resp_time=8
    ):
        self._proxies = proxies
        self._pool = []
        self._min_req_proxy = min_req_proxy
        # if num of erros greater or equal 50% - proxy will be remove from pool
        self._max_error_rate = max_error_rate
        self._max_resp_time = max_resp_time

    async def get(self, scheme):
        scheme = scheme.upper()
        for priority, proxy in self._pool:
            if scheme in proxy.schemes:
                chosen = proxy
                self._pool.remove((proxy.priority, proxy))
                break
        else:
            chosen = await self._import(scheme)
        return chosen

    async def _import(self, expected_scheme):
        while True:
            proxy = await self._proxies.get()
            self._proxies.task_done()
            if not proxy:
                raise NoProxyError('No more available proxies')
            elif expected_scheme not in proxy.schemes:
                self.put(proxy)
            else:
                return proxy

    def put(self, proxy):
        if proxy.stat['requests'] >= self._min_req_proxy and (
            (proxy.error_rate > self._max_error_rate)
            or (proxy.avg_resp_time > self._max_resp_time)
        ):
            log.debug(
                '%s:%d removed from proxy pool' % (proxy.host, proxy.port)
            )
        else:
            heapq.heappush(self._pool, (proxy.priority, proxy))
        log.debug('%s:%d stat: %s' % (proxy.host, proxy.port, proxy.stat))


class Server(asyncio.Protocol):
    """Server distributes incoming requests to a pool of found proxies."""

    def __init__(
        self,
        host,
        port,
        proxies,
        timeout=8,
        max_tries=3,
        min_req_proxy=5,
        max_error_rate=0.5,
        max_resp_time=8,
        prefer_connect=False,
        http_allowed_codes=None,
        backlog=100,
        loop=None,
        **kwargs,
    ):

        self.host = host
        self.port = int(port)
        self._loop = loop or asyncio.get_event_loop()
        self._timeout = timeout
        self._max_tries = max_tries
        self._backlog = backlog
        self._prefer_connect = prefer_connect

        self._server = None
        self._connections = {}
        self._proxy_pool = ProxyPool(
            proxies, min_req_proxy, max_error_rate, max_resp_time
        )
        self._resolver = Resolver(loop=self._loop)
        self._http_allowed_codes = http_allowed_codes or []

    async def start(self):
        # Creates the server instance.
        self._server = await self._loop.create_server(
            lambda: Interceptor(
                loop=self._loop,
                timeout=self._timeout,
                max_tries=self._max_tries,
                prefer_connect=self._prefer_connect,
                http_allowed_codes=self._http_allowed_codes,
                proxy_pool=self._proxy_pool,
                resolver=self._resolver,
            ),
            host=self.host,
            port=self.port,
        )

        # Prints information about the server.
        ip, port = self._server.sockets[0].getsockname()
        print("ProxyBroker initiated on {}:{}.\n".format(ip, port))

        try:
            # Starts the server instance.
            await self._server.serve_forever()
            print("server: _server.serve_forever()")
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        if not self._server:
            return
        for conn in self._connections:
            if not conn.done():
                conn.cancel()
        self._server.close()
        if not self._loop.is_running():
            self._loop.run_until_complete(self._server.wait_closed())
            # Time to close the running futures in self._connections
            self._loop.run_until_complete(asyncio.sleep(0.5))
        self._server = None
        self._loop.stop()
        log.info('Server is stopped')
