import time
import heapq
import asyncio

from .errors import *
from .utils import log, parse_headers, parse_status_line
from .resolver import Resolver


CONNECTED = b'HTTP/1.1 200 Connection established\r\n\r\n'


class ProxyPool:
    """Imports and gives proxies from queue on demand."""

    def __init__(self, proxies, min_req_proxy=5,
                 max_error_rate=0.5, max_resp_time=8):
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
        if (proxy.stat['requests'] >= self._min_req_proxy and
            ((proxy.error_rate > self._max_error_rate) or
             (proxy.avg_resp_time > self._max_resp_time))):
            log.debug('%s:%d removed from proxy pool' % (proxy.host, proxy.port))
        else:
            heapq.heappush(self._pool, (proxy.priority, proxy))
        log.debug('%s:%d stat: %s' % (proxy.host, proxy.port, proxy.stat))


class Server:
    """Server distributes incoming requests to a pool of found proxies."""

    def __init__(self, host, port, proxies, timeout=8, max_tries=3,
                 min_req_proxy=5, max_error_rate=0.5, max_resp_time=8,
                 prefer_connect=False, http_allowed_codes=None,
                 backlog=100, loop=None, **kwargs):
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
            proxies, min_req_proxy, max_error_rate, max_resp_time)
        self._resolver = Resolver(loop=self._loop)
        self._http_allowed_codes = http_allowed_codes or []

    def start(self):
        srv = asyncio.start_server(
            self._accept, host=self.host, port=self.port,
            backlog=self._backlog, loop=self._loop)
        self._server = self._loop.run_until_complete(srv)

        log.info('Listening established on {0}'.format(
            self._server.sockets[0].getsockname()))

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

    def _accept(self, client_reader, client_writer):
        def _on_completion(f):
            reader, writer = self._connections.pop(f)
            writer.close()
            log.debug('client: %d; closed' % id(client_reader))
            try:
                exc = f.exception()
            except asyncio.CancelledError:
                log.debug('CancelledError in server._handle:_on_completion')
                exc = None
            if exc:
                if isinstance(exc, NoProxyError):
                    self.stop()
                else:
                    raise exc
        f = asyncio.ensure_future(self._handle(client_reader, client_writer))
        f.add_done_callback(_on_completion)
        self._connections[f] = (client_reader, client_writer)

    async def _handle(self, client_reader, client_writer):
        log.debug('Accepted connection from %s' % (
                  client_writer.get_extra_info('peername'),))

        request, headers = await self._parse_request(client_reader)
        scheme = self._identify_scheme(headers)
        client = id(client_reader)
        log.debug('client: %d; request: %s; headers: %s; scheme: %s' % (
                  client, request, headers, scheme))

        for attempt in range(self._max_tries):
            stime, err = 0, None
            proxy = await self._proxy_pool.get(scheme)
            proto = self._choice_proto(proxy, scheme)
            log.debug('client: %d; attempt: %d; proxy: %s; proto: %s' % (
                      client, attempt, proxy, proto))
            try:
                await proxy.connect()

                if proto in ('CONNECT:80', 'SOCKS4', 'SOCKS5'):
                    host = headers.get('Host')
                    port = headers.get('Port', 80)
                    try:
                        ip = await self._resolver.resolve(host)
                    except ResolveError:
                        return
                    proxy.ngtr = proto
                    await proxy.ngtr.negotiate(host=host, port=port, ip=ip)
                    if scheme == 'HTTPS' and proto in ('SOCKS4', 'SOCKS5'):
                        client_writer.write(CONNECTED)
                        await client_writer.drain()
                    else:  # HTTP
                        await proxy.send(request)
                else:  # proto: HTTP & HTTPS
                    await proxy.send(request)

                stime = time.time()
                stream = [
                    asyncio.ensure_future(self._stream(
                        reader=client_reader, writer=proxy.writer)),
                    asyncio.ensure_future(self._stream(
                        reader=proxy.reader, writer=client_writer,
                        scheme=scheme))]
                await asyncio.gather(*stream, loop=self._loop)
            except asyncio.CancelledError:
                log.debug('Cancelled in server._handle')
                break
            except (ProxyTimeoutError, ProxyConnError, ProxyRecvError,
                    ProxySendError, ProxyEmptyRecvError, BadStatusError,
                    BadResponseError) as e:
                log.debug('client: %d; error: %r' % (client, e))
                continue
            except ErrorOnStream as e:
                log.debug('client: %d; error: %r; EOF: %s' % (
                          client, e, client_reader.at_eof()))
                for task in stream:
                    if not task.done():
                        task.cancel()
                if client_reader.at_eof() and 'Timeout' in repr(e):
                    # Proxy may not be able to receive EOF and weel be raised a
                    # TimeoutError, but all the data has already successfully
                    # returned, so do not consider this error of proxy
                    break
                err = e
                if scheme == 'HTTPS':  # SSL Handshake probably failed
                    break
            else:
                break
            finally:
                proxy.log(request.decode(), stime, err=err)
                proxy.close()
                self._proxy_pool.put(proxy)

    async def _parse_request(self, reader, length=65536):
        request = await reader.read(length)
        headers = parse_headers(request)
        if headers['Method'] == 'POST' and request.endswith(b'\r\n\r\n'):
            # For aiohttp. POST data returns on second reading
            request += await reader.read(length)
        return request, headers

    def _identify_scheme(self, headers):
        if headers['Method'] == 'CONNECT':
            return 'HTTPS'
        else:
            return 'HTTP'

    def _choice_proto(self, proxy, scheme):
        if scheme == 'HTTP':
            if self._prefer_connect and ('CONNECT:80' in proxy.types):
                proto = 'CONNECT:80'
            else:
                relevant = {'HTTP', 'CONNECT:80', 'SOCKS4', 'SOCKS5'} & proxy.types.keys()
                proto = relevant.pop()
        else:  # HTTPS
            relevant = {'HTTPS', 'SOCKS4', 'SOCKS5'} & proxy.types.keys()
            proto = relevant.pop()
        return proto

    async def _stream(self, reader, writer, length=65536, scheme=None):
        checked = False
        try:
            while not reader.at_eof():
                data = await asyncio.wait_for(reader.read(length), self._timeout)
                if not data:
                    writer.close()
                    break
                elif scheme and not checked:
                    self._check_response(data, scheme)
                    checked = True
                writer.write(data)
                await writer.drain()
        except (asyncio.TimeoutError, ConnectionResetError, OSError,
                ProxyRecvError, BadStatusError, BadResponseError) as e:
            raise ErrorOnStream(e)

    def _check_response(self, data, scheme):
        if scheme == 'HTTP' and self._http_allowed_codes:
            line = data.split(b'\r\n', 1)[0].decode()
            try:
                header = parse_status_line(line)
            except BadStatusLine:
                raise BadResponseError
            if header['Status'] not in self._http_allowed_codes:
                raise BadStatusError('%r not in %r' %(header['Status'], self._http_allowed_codes))
