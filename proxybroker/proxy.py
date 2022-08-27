import asyncio
import ssl as _ssl
import time
import warnings
from collections import Counter

from .errors import (
    ProxyConnError,
    ProxyEmptyRecvError,
    ProxyRecvError,
    ProxySendError,
    ProxyTimeoutError,
    ResolveError,
)
from .negotiators import NGTRS
from .resolver import Resolver
from .utils import log, parse_headers

_HTTP_PROTOS = {'HTTP', 'CONNECT:80', 'SOCKS4', 'SOCKS5'}
_HTTPS_PROTOS = {'HTTPS', 'SOCKS4', 'SOCKS5'}


class Proxy:
    """Proxy.

    :param str host: IP address of the proxy
    :param int port: Port of the proxy
    :param tuple types:
        (optional) List of types (protocols) which may be supported
        by the proxy and which can be checked to work with the proxy
    :param int timeout:
        (optional) Timeout of a connection and receive a response in seconds
    :param bool verify_ssl:
        (optional) Flag indicating whether to check the SSL certificates.
        Set to True to check ssl certifications

    :raises ValueError: If the host not is IP address, or if the port > 65535
    """

    @classmethod
    async def create(cls, host, *args, **kwargs):
        """Asynchronously create a :class:`Proxy` object.

        :param str host: A passed host can be a domain or IP address.
                         If the host is a domain, try to resolve it
        :param str *args:
            (optional) Positional arguments that :class:`Proxy` takes
        :param str **kwargs:
            (optional) Keyword arguments that :class:`Proxy` takes

        :return: :class:`Proxy` object
        :rtype: proxybroker.Proxy

        :raises ResolveError: If could not resolve the host
        :raises ValueError: If the port > 65535
        """  # noqa: W605
        loop = kwargs.pop('loop', None)
        resolver = kwargs.pop('resolver', Resolver(loop=loop))
        try:
            _host = await resolver.resolve(host)
            self = cls(_host, *args, **kwargs)
        except (ResolveError, ValueError) as e:
            log.error('%s:%s: Error at creating: %s' % (host, args[0], e))
            raise
        return self

    def __init__(self, host=None, port=None, types=(), timeout=8, verify_ssl=False):
        self.host = host
        if not Resolver.host_is_ip(self.host):
            raise ValueError(
                'The host of proxy should be the IP address. '
                'Try Proxy.create() if the host is a domain'
            )

        self.port = int(port)
        if self.port > 65535:
            raise ValueError('The port of proxy cannot be greater than 65535')

        self.expected_types = set(types) & {
            'HTTP',
            'HTTPS',
            'CONNECT:80',
            'CONNECT:25',
            'SOCKS4',
            'SOCKS5',
        }
        self._timeout = timeout
        self._ssl_context = True if verify_ssl else _ssl._create_unverified_context()
        self._types = {}
        self._is_working = False
        self.stat = {'requests': 0, 'errors': Counter()}
        self._ngtr = None
        self._geo = Resolver.get_ip_info(self.host)
        self._log = []
        self._runtimes = []
        self._schemes = ()
        self._closed = True
        self._reader = {'conn': None, 'ssl': None}
        self._writer = {'conn': None, 'ssl': None}

    def __repr__(self):
        """Class representation
        e.g. <Proxy US 1.12 [HTTP: Anonymous, HTTPS] 10.0.0.1:8080>
        """
        tpinfo = []
        order = lambda tp_lvl: (len(tp_lvl[0]), tp_lvl[0][-1])  # noqa: 731
        for tp, lvl in sorted(self.types.items(), key=order):
            s = '{tp}: {lvl}' if lvl else '{tp}'
            s = s.format(tp=tp, lvl=lvl)
            tpinfo.append(s)
        tpinfo = ', '.join(tpinfo)
        return '<Proxy {code} {avg:.2f}s [{types}] {host}:{port}>'.format(
            code=self._geo.code,
            types=tpinfo,
            host=self.host,
            port=self.port,
            avg=self.avg_resp_time,
        )

    @property
    def types(self):
        """Types (protocols) supported by the proxy.

        | Where key is type, value is level of anonymity
          (only for HTTP, for other types level always is None).
        | Available types: HTTP, HTTPS, SOCKS4, SOCKS5, CONNECT:80, CONNECT:25
        | Available levels: Transparent, Anonymous, High.

        :rtype: dict
        """
        return self._types

    @property
    def is_working(self):
        """True if the proxy is working, False otherwise.

        :rtype: bool
        """
        return self._is_working

    @is_working.setter
    def is_working(self, val):
        self._is_working = val

    @property
    def writer(self):
        return self._writer.get('ssl') or self._writer.get('conn')

    @property
    def reader(self):
        return self._reader.get('ssl') or self._reader.get('conn')

    @property
    def priority(self):
        return (self.error_rate, self.avg_resp_time)

    @property
    def error_rate(self):
        """Error rate: from 0 to 1.

        For example: 0.7 = 70% requests ends with error.

        :rtype: float

        .. versionadded:: 0.2.0
        """
        if not self.stat['requests']:
            return 0
        return round(sum(self.stat['errors'].values()) / self.stat['requests'], 2)

    @property
    def schemes(self):
        """Return supported schemes."""
        if not self._schemes:
            _schemes = []
            if self.types.keys() & _HTTP_PROTOS:
                _schemes.append('HTTP')
            if self.types.keys() & _HTTPS_PROTOS:
                _schemes.append('HTTPS')
            self._schemes = tuple(_schemes)
        return self._schemes

    @property
    def avg_resp_time(self):
        """The average connection/response time.

        :rtype: float
        """
        if not self._runtimes:
            return 0
        return round(sum(self._runtimes) / len(self._runtimes), 2)

    @property
    def avgRespTime(self):
        """
        .. deprecated:: 2.0
            Use :attr:`avg_resp_time` instead.
        """
        warnings.warn(
            '`avgRespTime` property is deprecated, ' 'use `avg_resp_time` instead.',
            DeprecationWarning,
        )
        return self.avg_resp_time

    @property
    def geo(self):
        """Geo information about IP address of the proxy.

        :return:
            Named tuple with fields:
                * ``code`` - ISO country code
                * ``name`` - Full name of country
                * ``region_code`` - ISO region code
                * ``region_name`` - Full name of region
                * ``city_name`` - Full name of city
        :rtype: collections.namedtuple

        .. versionchanged:: 0.2.0
            In previous versions return a dictionary, now named tuple.
        """
        return self._geo

    @property
    def ngtr(self):
        return self._ngtr

    @ngtr.setter
    def ngtr(self, proto):
        self._ngtr = NGTRS[proto](self)

    def as_json(self):
        """Return the proxy's properties in JSON format.

        :rtype: dict
        """
        info = {
            'host': self.host,
            'port': self.port,
            'geo': {
                'country': {'code': self._geo.code, 'name': self._geo.name},
                'region': {
                    'code': self._geo.region_code,
                    'name': self._geo.region_name,
                },
                'city': self._geo.city_name,
            },
            'types': [],
            'avg_resp_time': self.avg_resp_time,
            'error_rate': self.error_rate,
        }

        order = lambda tp_lvl: (len(tp_lvl[0]), tp_lvl[0][-1])  # noqa: 731
        for tp, lvl in sorted(self.types.items(), key=order):
            info['types'].append({'type': tp, 'level': lvl or ''})
        return info

    def as_text(self):
        """
        Return proxy as host:port

        :rtype: str
        """
        return "{}:{}\n".format(self.host, self.port)

    def log(self, msg, stime=0, err=None):
        ngtr = self.ngtr.name if self.ngtr else 'INFO'
        runtime = time.time() - stime if stime else 0
        log.debug(
            '{h}:{p} [{n}]: {msg}; Runtime: {rt:.2f}'.format(
                h=self.host, p=self.port, n=ngtr, msg=msg, rt=runtime
            )
        )
        trunc = '...' if len(msg) > 58 else ''
        msg = '{msg:.60s}{trunc}'.format(msg=msg, trunc=trunc)
        self._log.append((ngtr, msg, runtime))
        if err:
            self.stat['errors'][err.errmsg] += 1
        if runtime and 'timeout' not in msg:
            self._runtimes.append(runtime)

    def get_log(self):
        """Proxy log.

        :return: The proxy log in format: (negotaitor, msg, runtime)
        :rtype: tuple

        .. versionadded:: 0.2.0
        """
        return self._log

    async def connect(self, ssl=False):
        err = None
        msg = '%s' % 'SSL: ' if ssl else ''
        stime = time.time()
        self.log('%sInitial connection' % msg)
        try:
            if ssl:
                _type = 'ssl'
                sock = self._writer['conn'].get_extra_info('socket')
                params = {
                    'ssl': self._ssl_context,
                    'sock': sock,
                    'server_hostname': self.host,
                }
            else:
                _type = 'conn'
                params = {'host': self.host, 'port': self.port}
            self._reader[_type], self._writer[_type] = await asyncio.wait_for(
                asyncio.open_connection(**params), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            msg += 'Connection: timeout'
            err = ProxyTimeoutError(msg)
            raise err
        except (ConnectionRefusedError, OSError, _ssl.SSLError):
            msg += 'Connection: failed'
            err = ProxyConnError(msg)
            raise err
        # except asyncio.CancelledError:
        #     log.debug('Cancelled in proxy.connect()')
        #     raise ProxyConnError()
        else:
            msg += 'Connection: success'
            self._closed = False
        finally:
            self.stat['requests'] += 1
            self.log(msg, stime, err=err)

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self.writer:
            # try:
            self.writer.close()
            # except RuntimeError:
            #     print('Try proxy.close() when loop is closed:',
            #           asyncio.get_event_loop()._closed)
        self._reader = {'conn': None, 'ssl': None}
        self._writer = {'conn': None, 'ssl': None}
        self.log('Connection: closed')
        self._ngtr = None

    async def send(self, req):
        msg, err = '', None
        _req = req.encode() if not isinstance(req, bytes) else req
        try:
            self.writer.write(_req)
            await self.writer.drain()
        except ConnectionResetError:
            msg = '; Sending: failed'
            err = ProxySendError(msg)
            raise err
        finally:
            self.log('Request: %s%s' % (req, msg), err=err)

    async def recv(self, length=0, head_only=False):
        resp, msg, err = b'', '', None
        stime = time.time()
        try:
            resp = await asyncio.wait_for(
                self._recv(length, head_only), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            msg = 'Received: timeout'
            err = ProxyTimeoutError(msg)
            raise err
        except (ConnectionResetError, OSError):
            msg = 'Received: failed'  # (connection is reset by the peer)
            err = ProxyRecvError(msg)
            raise err
        else:
            msg = 'Received: %s bytes' % len(resp)
            if not resp:
                err = ProxyEmptyRecvError(msg)
                raise err
        finally:
            if resp:
                msg += ': %s' % resp[:12]
            self.log(msg, stime, err=err)
        return resp

    async def _recv(self, length=0, head_only=False):
        resp = b''
        if length:
            try:
                resp = await self.reader.readexactly(length)
            except asyncio.IncompleteReadError as e:
                resp = e.partial
        else:
            body_size, body_recv, chunked = 0, 0, None
            while not self.reader.at_eof():
                line = await self.reader.readline()
                resp += line
                if body_size:
                    body_recv += len(line)
                    if body_recv >= body_size:
                        break
                elif chunked and line == b'0\r\n':
                    break
                elif not body_size and line == b'\r\n':
                    if head_only:
                        break
                    headers = parse_headers(resp)
                    body_size = int(headers.get('Content-Length', 0))
                    if not body_size:
                        chunked = headers.get('Transfer-Encoding') == 'chunked'
        return resp
