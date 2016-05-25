import time
import asyncio
import warnings
import ssl as _ssl
from collections import Counter

from .errors import *
from .utils import log
from .resolver import Resolver
from .negotiators import NGTRS


warnings.simplefilter('once', DeprecationWarning)


_HTTP_PROTOS = {'HTTP', 'CONNECT:80', 'SOCKS4', 'SOCKS5'}
_HTTPS_PROTOS = {'HTTPS', 'SOCKS4', 'SOCKS5'}


class Proxy:
    """Proxy."""

    @classmethod
    async def create(cls, host, *args, **kwargs):
        loop = kwargs.pop('loop', None)
        resolver = kwargs.pop('resolver', Resolver(loop=loop))
        _host = await resolver.resolve(host)
        if not _host:
            return
        try:
            self = cls(_host, *args, **kwargs)
        except ValueError as e:
            log.error('%s:%s::: %s' % (host, args[0], e))
            return
        return self

    def __init__(self, host=None, port=None, types=(),
                 timeout=8, verify_ssl=False):
        self.host = host
        if not Resolver.host_is_ip(self.host):
            raise ValueError('The host of proxy should be the IP address. '
                             'Try Proxy.create() if the host is a domain')

        self.port = int(port)
        if self.port > 65535:
            raise ValueError('The port of proxy cannot be greater than 65535')

        self.expected_types = set(types) & {'HTTP', 'HTTPS', 'CONNECT:80',
                                            'CONNECT:25', 'SOCKS4', 'SOCKS5'}
        self._timeout = timeout
        self._ssl_context = True if verify_ssl else _ssl._create_unverified_context()

        self.types = {}
        self.is_working = False
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
        # <Proxy US 1.12 [HTTP: Anonymous, HTTPS] 10.0.0.1:8080>
        tpinfo = []
        order = lambda tp_lvl: (len(tp_lvl[0]), tp_lvl[0][-1])
        for tp, lvl in sorted(self.types.items(), key=order):
            s = '{tp}: {lvl}' if lvl else '{tp}'
            s = s.format(tp=tp, lvl=lvl)
            tpinfo.append(s)
        tpinfo = ', '.join(tpinfo)
        return '<Proxy {code} {avg:.2f}s [{types}] {host}:{port}>'.format(
               code=self._geo.code, types=tpinfo, host=self.host,
               port=self.port, avg=self.avg_resp_time)

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

        By example: 0.7 = 70% requests ends with error.
        """
        return sum(self.stat['errors'].values()) / self.stat['requests']

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
        """Return the average connection/response time."""
        if self._runtimes:
            return sum(self._runtimes) / len(self._runtimes)
        else:
            return 0

    @property
    def avgRespTime(self):
        warnings.warn('`avgRespTime` property is deprecated, '
                      'use `avg_resp_time` instead.', DeprecationWarning)
        return self.avg_resp_time

    @property
    def geo(self):
        return self._geo

    @property
    def ngtr(self):
        return self._ngtr

    @ngtr.setter
    def ngtr(self, proto):
        self._ngtr = NGTRS[proto](self)

    def log(self, msg, stime=0, err=None):
        ngtr = self.ngtr.name if self.ngtr else 'INFO'
        runtime = time.time() - stime if stime else 0
        log.debug('{h}:{p} [{n}]: {msg}; Runtime: {rt:.2f}'.format(
            h=self.host, p=self.port, n=ngtr, msg=msg, rt=runtime))
        trunc = '...' if len(msg) > 58 else ''
        msg = '{msg:.60s}{trunc}'.format(msg=msg, trunc=trunc)
        self._log.append((ngtr, msg, runtime))
        if err:
            self.stat['errors'][err.errmsg] += 1
        if runtime and 'timeout' not in msg:
            self._runtimes.append(runtime)

    def get_log(self):
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
                params = {'ssl': self._ssl_context, 'sock': sock, 'server_hostname': self.host}
            else:
                _type = 'conn'
                params = {'host': self.host, 'port': self.port}
            self._reader[_type], self._writer[_type] = \
                await asyncio.wait_for(asyncio.open_connection(**params),
                                       timeout=self._timeout)
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
        if self.writer:
            self.writer.close()
        self._closed = True
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

    async def recv(self, length=65536, one_chunk=False):
        resp, msg, err = b'', '', None
        stime = time.time()
        try:
            while not self.reader.at_eof() and len(resp) < length:
                data = await asyncio.wait_for(
                    self.reader.read(length), timeout=self._timeout)
                resp += data
                if not data or one_chunk:
                    break
        except asyncio.TimeoutError:
            msg = 'Received: timeout'
            err = ProxyTimeoutError(msg)
            raise err
        except (ConnectionResetError, OSError) as e:
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
