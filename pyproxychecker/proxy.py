import re
import time
import asyncio
import logging
from collections import defaultdict, Counter, Iterable

from .errors import *
from .utils import mmdbReader

log = logging.getLogger(__package__)


class Proxy:
    # _log = defaultdict(list)
    # _errors = defaultdict(Counter)
    # _expectedType = dict()
    # _runtimes = defaultdict(list)
    # _anonymity = defaultdict(dict)
    myRealIP = None
    IPPattern = re.compile(
        b'(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}'
        b'(?:25[0-5]|2[0-4]\d|[01]?\d\d?)')

    def __init__(self, host=None, port=None, types=[],
                 ancestor=None, ngtr=None, judge=None):
        if ancestor:
            host = ancestor.host
            port = ancestor.port
            judge = ancestor.judge
            self._log = ancestor._log
            self.errors = ancestor.errors
            self.types = ancestor.types
            self.runtimes = ancestor.runtimes
        else:
            self._log = []
            self.errors = Counter()
            self.types = {}
            self.runtimes = []

        self.host = host
        self.port = int(port)
        self._types = self.check_inp_types(types)

        self.ngtr = ngtr
        self.judge = judge

        self.isWorking = None
        self.reader = None
        self.writer = None
        self.geo = {}
        self.avgRespTime = None
        # self.geo = {'country': {'code': None, 'name': None}}
        # 'city': {'code': None, 'name': None},


    def check_on_errors(self, msg):
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

    def get_descendant(self, ngtr):
        descendant = Proxy(ancestor=self, ngtr=ngtr.name)
        return descendant

    # @staticmethod
    def check_inp_types(self, types):
        if isinstance(types, str):
            types = types.split(',')
        elif isinstance(types, (list, tuple)):
            pass
        else:
            raise ProxyTypeError
        return [t for t in types if t in ['HTTP', 'HTTPS', 'CONNECT',
                                          'SOCKS4', 'SOCKS5']]

    # @staticmethod
    # def check_inp_anonymity(lvls):
    #     if isinstance(lvls, str):
    #         lvls = lvls.split(',')
    #     elif isinstance(lvls, Iterable):
    #         pass
    #     else:
    #         raise ProxyAnonLvlError
    #     return [l for l in lvls if l in ['Transparent', 'Anonymous', 'High']]

    # @staticmethod
    # def check_inp_country(country):
    #     if isinstance(country, str):
    #         country = country.split(',')
    #     elif isinstance(country, Iterable):
    #         pass
    #     else:
    #         raise ProxyISOCountryError
    #     return [c for c in country if len(c) == 2]

    def set_geo(self):
        try:
            ipInfo = mmdbReader.get(self.host)
        except InvalidDatabaseError:
            pass
        else:
            self.geo = ipInfo['country']

    def set_avg_resp_time(self):
        if not self.types:
            self.avgRespTime = 0
        else:
            self.avgRespTime = '%.2f' % (sum(self.runtimes)/len(self.runtimes))

    def log(self, msg=None, stime=None):
        if msg:
            runtime = time.time()-stime if stime else 0
            log.debug('{host}: {ngtr}: {msg}; Runtime: {rt:.4f}'.format(
                host=self.host, ngtr=self.ngtr, msg=msg, rt=runtime))
            msg = '{ngtr}: {msg:.58s}{trunc}'.format(
                ngtr=self.ngtr, msg=msg, trunc='...' if len(msg) > 58 else '')
            self._log.append((msg, runtime))
            self.check_on_errors(msg)
            if runtime and 'timeout' not in msg:
                # self.runtimes.append((self.ngtr, runtime))
                self.runtimes.append(runtime)
        else:
            return self._log

    # @property
    # def reader(self):
    #     return self._reader

    # @reader.setter
    # def reader(self, ngtr):
    #     self._reader[ngtr]

    # writer

    # @property
    # def anonymity(self):
    #     return self._anonymity
    #     # return self._anonymity.get(self.host)

    # @anonymity.setter
    # def anonymity(self, lvl):
    #     self._anonymity[self.ngtr] = lvl
    #     # print('set anonymity for %s: %r:::all:%r' % (self.host, self.anonymity[self.ngtr], self.anonymity))
    #     # self._anonymity[self.host][self.ngtr] = lvl

    # @property
    # def expected_type(self):
    #     return self._expectedType.get(self.host, False)

    # @expected_type.setter
    # def expected_type(self, t):
    #     self._expectedType[self.host] = t

    async def connect(self):
        self.log('Initial connection')
        stime = time.time()
        try:
            self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=self.timeout)
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

    async def send(self, req):
        self.log('Request: %s' % (req))
        self.writer.write(req)
        try:
            await self.writer.drain()
        except ConnectionResetError:
            msg = 'Sending: failed;'
            self.log(msg)
            raise ProxyRecvError(msg)

    async def recv(self, length):
        resp = ''
        stime = time.time()
        try:
            resp = await asyncio.wait_for(
                self.reader.read(length), timeout=self.timeout)
            msg = 'Received: %s bytes' % len(resp)
        except asyncio.TimeoutError:
            msg = 'Received: timeout'
            raise ProxyTimeoutError(msg)
        except (ConnectionResetError, OSError):
            # OSError - [Errno 9] Bad file descriptor
            msg = 'Received: failed'  # (connection is reset by the peer)
            raise ProxyRecvError(msg)
        else:
            if not resp:
                # self.log('Failed (empty response)')
                raise ProxyEmptyRecvError(msg)
        finally:
            if resp:
                msg += ': %s' % resp[:12]
            self.log(msg, stime)
            # log.debug('%s: Response: %r', self.host, resp)
        return resp

    async def check_get_request(self):  # scheme
        _dest = dict(host=self.judge.host, path=self.judge.path)
        if self.ngtr == 'HTTP':
            # set full URL for HTTP-negotiator
            _dest['path'] = 'http://{host}{path}'.format(**_dest)

        req = ('GET {path} HTTP/1.1\r\nHost: {host}\r\n'
              'Accept: *.*, */*\r\nConnection: close\r\n\r\n')\
              .format(**_dest).encode()

        stime = time.time()
        try:
            await self.send(req)
            resp = await self.recv(-1) # self.dest['length']
        except (ProxyTimeoutError, ProxyRecvError):
            return
        except ProxyEmptyRecvError:
            if self.ngtr == 'HTTP':
                return False
            else:
                return

        httpStatusCode = resp[9:12]
        if httpStatusCode == b'200':
            # and self.dest['search'].encode() in resp
            self.check_anonymity(resp)
            self.log('Get: success', stime)
            return True
        else:
            self.log('Get: failed; HTTP status: %s' % httpStatusCode, stime)
            # self.log('Get: failed; Resp: %s' % resp, stime)
            return False

    def check_anonymity(self, resp):
        resp = resp.lower()
        foundIP = set(self.IPPattern.findall(resp))
        via = b'via' in resp
        prx = b'proxy' in resp
        if self.myRealIP in foundIP:
            self.types[self.ngtr] = 'Transparent'
        elif via or prx:
            self.types[self.ngtr] = 'Anonymous'
        else:
            self.types[self.ngtr] = 'High'

        # log.debug('Resp: %s' % resp)
        self.log('A: {lvl}; {ip}; via(p): {via};'.format(
            lvl=self.types[self.ngtr][:4], ip=foundIP, via=via or prx))
        # _, body = resp.decode().split('\r\n\r\n')
        # data = json.loads(body)

    def __repr__(self):
        if self.types:
            types = ', '.join(['{tp}: {anonLvl}'.format(tp=k, anonLvl=v)
                               for k, v in self.types.items()])
        else:
            types = '-'

        code = '%s ' % self.geo.get('iso_code', '')
        # name = self.geo['names']['en'] if self.geo else ''
        return '<Proxy {code}{avg}s [{types}] {host}:{port}>'.format(
               code=code, types=types, host=self.host, port=self.port,
               avg=self.avgRespTime)
        # <Proxy US [HTTP: Anonymous, HTTPS: High] 10.0.0.1:8080>,
        # Runtime: {avg}  avg=self.get_avg_runtime()
