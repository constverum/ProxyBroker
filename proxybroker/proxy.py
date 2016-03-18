import ssl
import time
import asyncio
from collections import Counter

from .errors import *
from .judge import Judge
from .utils import log, get_ip_info, get_my_ip, get_all_ip,\
                   get_headers, host_is_ip, resolve_host


class Proxy:
    _sem = None
    _loop = None
    _timeout = None
    _verifySSL = False
    sslContext = True if _verifySSL else\
                 ssl._create_unverified_context()

    @classmethod
    async def create(cls, host, port, *args):
        self = cls(host, port, *args)
        await self._resolve_host()
        if self.host is False or self.port > 65535:
            return False
        else:
            return self

    def __init__(self, host=None, port=None, types=[],
                 ancestor=None, ngtr=None, judge=None):
        if ancestor:
            host = ancestor.host
            port = ancestor.port
            self.sem = ancestor.sem
            self.types = ancestor.types
            self.errors = ancestor.errors
            self._log = ancestor._log
            self._runtimes = ancestor._runtimes
            self._expectedType = ancestor._expectedType
        else:
            self.types = {}
            self.errors = Counter()
            self.sem = asyncio.Semaphore(4)  # Concurrent requests to the proxy
            self._log = []
            self._runtimes = []
            self._descendants = []
            self._expectedType = {'_': None}

        self.host = host
        self.port = int(port)

        self.judge = judge
        self.isWorking = None
        self.avgRespTime = ''

        self._geo = {}
        self._ngtr = ngtr
        self._inp_types = self._check_inp_types(types)
        self._isClosed = False
        self.__reader = {'conn': None, 'ssl': None}
        self.__writer = {'conn': None, 'ssl': None}

    def __repr__(self):
        # <Proxy US 1.12 [HTTP: Anonymous, HTTPS] 10.0.0.1:8080>
        tpinfo = []
        for tp, lvl in sorted(self.types.items()):
            s = '{tp}: {lvl}' if lvl else '{tp}'
            s = s.format(tp=tp, lvl=lvl)
            tpinfo.append(s)
        tpinfo = ', '.join(tpinfo)
        return '<Proxy {code} {avg} [{types}] {host}:{port}>'.format(
               code=self.geo['code'], types=tpinfo, host=self.host,
               port=self.port, avg=self.avgRespTime)

    @property
    def _writer(self):
        return self.__writer.get('ssl') or self.__writer.get('conn')

    @property
    def _reader(self):
        return self.__reader.get('ssl') or self.__reader.get('conn')

    def _check_inp_types(self, types):
        if isinstance(types, str):
            types = types.split(',')
        elif isinstance(types, (list, tuple, set)):
            pass
        else:
            raise ProxyTypeError
        return [t for t in types if t in ['HTTP', 'HTTPS', 'CONNECT',
                                          'SOCKS4', 'SOCKS5']]

    def _check_on_errors(self, msg):
        err = None
        if 'Connection: timeout' in msg:
            err = 'connection_timeout'
        elif 'Connection: failed' in msg:
            err = 'connection_failed'
        elif 'Received: timeout' in msg:
            err = 'received_timeout'
        elif 'Received: failed' in msg:
            err = 'connection_is_reset'
        elif 'Received: 0 bytes' in msg:
            err = 'empty_response'
        elif 'SSL: UNKNOWN_PROTOCOL' in msg:
            err = 'ssl_unknown_protocol'
        elif 'SSL: CERTIFICATE_VERIFY_FAILED' in msg:
            err = 'ssl_verified_failed'
        if err:
            self.errors[err] += 1

    def _get_descendant(self, ngtr):
        judge = Judge.get_random('HTTPS' if ngtr.name == 'HTTPS' else 'HTTP')
        self.log('{:>36}: {}'.format('Selected judge', judge))
        descendant = Proxy(ancestor=self, ngtr=ngtr.name, judge=judge)
        self._descendants.append(descendant)
        return descendant

    @property
    def geo(self):
        if not self._geo:
            self._set_geo()
        return self._geo

    def _set_geo(self):
        self._geo['code'], self._geo['name'] = get_ip_info(self.host)

    def log(self, msg=None, stime=None):
        if msg:
            runtime = time.time()-stime if stime else 0
            log.debug('{host}: {ngtr}: {msg}; Runtime: {rt:.4f}'.format(
                host=self.host, ngtr=self._ngtr, msg=msg, rt=runtime))
            msg = '{ngtr}: {msg:.58s}{trunc}'.format(
                ngtr=self._ngtr, msg=msg, trunc='...' if len(msg) > 58 else '')
            self._log.append((msg, runtime))
            self._check_on_errors(msg)
            if runtime and 'timeout' not in msg:
                self._runtimes.append(runtime)
        else:
            return self._log

    @property
    def expectedType(self):
        return self._expectedType['_']

    @expectedType.setter
    def expectedType(self, t):
        self._expectedType['_'] = t

    async def connect(self):
        self.log('Initial connection')
        stime = time.time()
        msg = ''
        try:
            conn = asyncio.open_connection(self.host, self.port)
            self.__reader['conn'], self.__writer['conn'] = \
                await asyncio.wait_for(conn, timeout=self._timeout)
        except asyncio.TimeoutError:
            msg = 'Connection: timeout'
            raise ProxyTimeoutError(msg)
        except (ConnectionRefusedError, OSError):
            msg = 'Connection: failed'
            raise ProxyConnError(msg)
        else:
            msg = 'Connection: success'
        finally:
            self.log(msg, stime)

    def close(self):
        self._isClosed = True
        if self._writer:
            self._writer.close()
        self.log('Connection: closed')

    async def send(self, req):
        # self.log('writer: %s' % self._writer)
        self.log('Request: %s' % (req))
        try:
            self._writer.write(req)
            await self._writer.drain()
        except ConnectionResetError:
            msg = 'Sending: failed;'
            self.log(msg)
            raise ProxyRecvError(msg)

    async def recv(self, length=-1):
        # self.log('reader: %s' % self._reader)
        resp, msg = '', ''
        stime = time.time()
        try:
            resp = await asyncio.wait_for(
                self._reader.read(length), timeout=self._timeout)
        except asyncio.TimeoutError:
            msg = 'Received: timeout'
            raise ProxyTimeoutError(msg)
        except (ConnectionResetError, OSError) as e:
            msg = 'Received: failed'  # (connection is reset by the peer)
            raise ProxyRecvError(msg)
        else:
            msg = 'Received: %s bytes' % len(resp)
            if not resp:
                raise ProxyEmptyRecvError(msg)
        finally:
            if resp:
                msg += ': %s' % resp[:12]
            self.log(msg, stime)
        return resp

    def _GET_request(self):
        dest = {'host': self.judge.host,
                'path': self.judge.path if self._ngtr != 'HTTP' else\
                        'http://%s%s' % (self.judge.host, self.judge.path)}
        headers, rv = get_headers(rv=True)
        request = (
            'GET {path} HTTP/1.1\r\nHost: {host}\r\n'+
            '\r\n'.join(('%s: %s' % (k, v) for k, v in headers.items()))+
            '\r\nConnection: close\r\n\r\n')
        request = request.format(**dest).encode()
        return request, rv

    def _CONNECT_request(self):
        headers = get_headers()
        request = (
            'CONNECT {host}:443 HTTP/1.1\r\nHost: {host}\r\n'
            'User-Agent: {ua}\r\nConnection: keep-alive\r\n\r\n').format(
                host=self.judge.host, ua=headers['User-Agent']).encode()
        return request

    async def check_working(self):
        if self._ngtr == 'HTTPS':
            res = await self._ssl_wrap_connection()
            if not res:
                return res

        stime = time.time()
        request, rv = self._GET_request()
        resp = None

        try:
            await self.send(request)
            resp = await self.recv()
        except (ProxyTimeoutError, ProxyRecvError):
            return
        except ProxyEmptyRecvError:
            return False if self._ngtr == 'HTTP' else None
        finally:
            log.debug('{h}: ({j}) rv: {rv}; response: {resp}'.format(
                h=self.host, j=self.judge.url, rv=rv, resp=resp))

        try:
            headers, content, *_ = resp.split(b'\r\n\r\n', maxsplit=1)
            content = content.decode('utf-8', 'replace')
            httpStatusCode = int(headers[9:12])
        except ValueError:
            return False

        verIsCorrect = rv in content
        foundIP = get_all_ip(content)

        if httpStatusCode == 200 and verIsCorrect and foundIP:
            if self._ngtr == 'HTTP':
                self.check_anonymity(content, foundIP)
            else:
                self.types[self._ngtr] = None
            # self.check_anonymity(content, foundIP)
            self.log('Get: success', stime)
            return True
        else:
            self.log('Get: failed; HTTP status: %d; rv: %s' % (
                httpStatusCode, verIsCorrect), stime)
            return False

    def check_anonymity(self, content, foundIP):
        content = content.lower()
        via = (content.count('via') > self.judge.marks['via']) or\
              (content.count('proxy') > self.judge.marks['proxy'])

        if get_my_ip() in foundIP:
            self.types[self._ngtr] = 'Transparent'
        elif via:
            self.types[self._ngtr] = 'Anonymous'
        else:
            self.types[self._ngtr] = 'High'

        self.log('A: {lvl}; {ip}; via(p): {via}'.format(
            lvl=self.types[self._ngtr][:4], ip=foundIP, via=via))

    async def check(self, ngtrs):
        ngtrs = [ngtrs.get(n) for n in self._inp_types or ngtrs]

        try:
            results = await asyncio.gather(*[n(p=self._get_descendant(ngtr=n))
                                             for n in ngtrs if n])
        finally:
            while self._descendants:
                p = self._descendants.pop()
                if not p._isClosed:
                    p.close()
                    del p

        self.isWorking = True if any(results) else False

        if self.isWorking:
            self._set_avg_resp_time()

    def _set_avg_resp_time(self):
        self.avgRespTime = '' if not self.types else\
            '%.2fs' % (sum(self._runtimes[1:])/len(self._runtimes[1:]))

    async def _resolve_host(self):
        stime = time.time()
        if host_is_ip(self.host):
            return
        name = self.host
        with (await self._sem):
            self.host = await resolve_host(self.host, self._timeout, self._loop)
        if self.host:
            msg = 'Host resolved (orig. name: %s)' % name
        else:
            msg = 'Could not resolve host'
        self.log(msg, stime)

    async def _ssl_wrap_connection(self):
        # like aiohttp/connector.py ProxyConnector._create_connection()
        stime = time.time()
        msg = ''
        try:
            # self._writer.transport.pause_reading()
            conn = asyncio.open_connection(
                        ssl=self.sslContext,
                        sock=self._writer.get_extra_info('socket'),
                        server_hostname=self.host)
            self.__reader['ssl'], self.__writer['ssl'] = \
                await asyncio.wait_for(conn, timeout=self._timeout)
        except (ConnectionResetError, OSError) as e:
            msg = 'SSL: failed'
            return
        except asyncio.TimeoutError:
            msg = 'SSL: timeout'
            return
        except ssl.SSLError as e:
            msg = 'SSL: %s' % e
            return False
        else:
            msg = 'SSL: enabled'
            return True
        finally:
            self.log(msg, stime)
