import asyncio
import time
import warnings
import zlib

from .errors import (
    BadResponseError,
    BadStatusError,
    ProxyConnError,
    ProxyEmptyRecvError,
    ProxyRecvError,
    ProxySendError,
    ProxyTimeoutError,
    ResolveError,
)
from .judge import Judge, get_judges
from .negotiators import NGTRS
from .resolver import Resolver
from .utils import get_all_ip, get_headers, get_status_code, log, parse_headers


class Checker:
    """Proxy checker."""

    def __init__(
        self,
        judges,
        max_tries=3,
        timeout=8,
        verify_ssl=False,
        strict=False,
        dnsbl=None,
        real_ext_ip=None,
        types=None,
        post=False,
        loop=None,
    ):
        Judge.clear()
        self._judges = get_judges(judges, timeout, verify_ssl)
        self._method = 'POST' if post else 'GET'
        self._max_tries = max_tries
        self._real_ext_ip = real_ext_ip
        self._strict = strict
        self._dnsbl = dnsbl or []
        self._types = types or {}
        self._loop = loop or asyncio.get_event_loop()
        self._resolver = Resolver(loop=self._loop)

        self._req_http_proto = not types or bool(
            ('HTTP', 'CONNECT:80', 'SOCKS4', 'SOCKS5') & types.keys()
        )
        self._req_https_proto = not types or bool(('HTTPS',) & types.keys())
        self._req_smtp_proto = not types or bool(('CONNECT:25',) & types.keys())  # noqa

        self._ngtrs = {proto for proto in types or NGTRS}

    async def check_judges(self):
        # TODO: need refactoring
        log.debug('Start check judges')
        stime = time.time()
        await asyncio.gather(
            *[j.check(real_ext_ip=self._real_ext_ip) for j in self._judges]
        )

        self._judges = [j for j in self._judges if j.is_working]
        log.debug(
            '%d judges added. Runtime: %.4f;' % (len(self._judges), time.time() - stime)
        )

        nojudges = []
        disable_protocols = []

        if len(Judge.available['HTTP']) == 0:
            nojudges.append('HTTP')
            disable_protocols.extend(['HTTP', 'CONNECT:80', 'SOCKS4', 'SOCKS5'])
            self._req_http_proto = False
            # for coroutines, which is already waiting
            Judge.ev['HTTP'].set()
        if len(Judge.available['HTTPS']) == 0:
            nojudges.append('HTTPS')
            disable_protocols.append('HTTPS')
            self._req_https_proto = False
            # for coroutines, which is already waiting
            Judge.ev['HTTPS'].set()
        if len(Judge.available['SMTP']) == 0:
            # nojudges.append('SMTP')
            disable_protocols.append('SMTP')
            self._req_smtp_proto = False
            # for coroutines, which is already waiting
            Judge.ev['SMTP'].set()

        for proto in disable_protocols:
            if proto in self._ngtrs:
                self._ngtrs.remove(proto)

        if nojudges:
            warnings.warn(
                'Not found judges for the {nojudges} protocol.\n'
                'Checking proxy on protocols {disp} is disabled.'.format(
                    nojudges=nojudges, disp=disable_protocols
                ),
                UserWarning,
            )
        if self._judges:
            log.debug('Loaded: %d proxy judges' % len(set(self._judges)))
        else:
            RuntimeError('Not found judges')

    def _types_passed(self, proxy):
        if not self._types:
            return True
        for proto, lvl in proxy.types.copy().items():
            req_levels = self._types.get(proto)
            if not req_levels or (lvl in req_levels):
                if not self._strict:
                    return True
            else:
                if self._strict:
                    del proxy.types[proto]
        if self._strict and proxy.types:
            return True
        proxy.log('Protocol or the level of anonymity differs from the requested')
        return False

    async def _in_DNSBL(self, host):
        _host = '.'.join(reversed(host.split('.')))  # reverse address
        tasks = []
        for domain in self._dnsbl:
            query = '.'.join([_host, domain])
            tasks.append(self._resolver.resolve(query, logging=False))
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        if any([r for r in responses if not isinstance(r, ResolveError)]):
            return True
        return False

    async def check(self, proxy):
        if self._dnsbl:
            if await self._in_DNSBL(proxy.host):
                proxy.log('Found in DNSBL')
                return False

        if self._req_http_proto:
            await Judge.ev['HTTP'].wait()
        if self._req_https_proto:
            await Judge.ev['HTTPS'].wait()
        if self._req_smtp_proto:
            await Judge.ev['SMTP'].wait()

        if proxy.expected_types:
            ngtrs = proxy.expected_types & self._ngtrs
        else:
            ngtrs = self._ngtrs

        results = []
        for proto in ngtrs:
            if proto == 'CONNECT:25':
                result = await self._check_conn_25(proxy, proto)
            else:
                result = await self._check(proxy, proto)
            results.append(result)

        proxy.is_working = True if any(results) else False

        if proxy.is_working and self._types_passed(proxy):
            return True
        return False

    async def _check_conn_25(self, proxy, proto):
        judge = Judge.get_random(proto)
        proxy.log('Selected judge: %s' % judge)
        result = False
        for attempt in range(self._max_tries):
            try:
                proxy.ngtr = proto
                await proxy.connect()
                await proxy.ngtr.negotiate(host=judge.host, ip=judge.ip)
            except ProxyTimeoutError:
                continue
            except (
                ProxyConnError,
                ProxyRecvError,
                ProxySendError,
                ProxyEmptyRecvError,
                BadStatusError,
                BadResponseError,
            ):
                break
            else:
                proxy.types[proxy.ngtr.name] = None
                result = True
                break
            finally:
                proxy.close()
        return result

    async def _check(self, proxy, proto):
        judge = Judge.get_random(proto)
        proxy.log('Selected judge: %s' % judge)
        result = False
        for attempt in range(self._max_tries):
            try:
                proxy.ngtr = proto
                await proxy.connect()
                await proxy.ngtr.negotiate(host=judge.host, ip=judge.ip)
                headers, content, rv = await _send_test_request(
                    self._method, proxy, judge
                )
            except ProxyTimeoutError:
                continue
            except (
                ProxyConnError,
                ProxyRecvError,
                ProxySendError,
                ProxyEmptyRecvError,
                BadStatusError,
                BadResponseError,
            ):
                break
            else:
                content = _decompress_content(headers, content)
                result = _check_test_response(proxy, headers, content, rv)
                if result:
                    if proxy.ngtr.check_anon_lvl:
                        lvl = _get_anonymity_lvl(
                            self._real_ext_ip, proxy, judge, content
                        )
                    else:
                        lvl = None
                    proxy.types[proxy.ngtr.name] = lvl
                break
            finally:
                proxy.close()
        return result


def _request(method, host, path, fullpath=False, data=''):
    hdrs, rv = get_headers(rv=True)
    hdrs['Host'] = host
    hdrs['Connection'] = 'close'
    hdrs['Content-Length'] = len(data)
    if method == 'POST':
        hdrs['Content-Type'] = 'application/octet-stream'
    kw = {
        'method': method,
        'path': 'http://%s%s' % (host, path) if fullpath else path,  # HTTP
        'headers': '\r\n'.join(('%s: %s' % (k, v) for k, v in hdrs.items())),
        'data': data,
    }
    req = ('{method} {path} HTTP/1.1\r\n{headers}\r\n\r\n{data}').format(**kw).encode()
    return req, rv


async def _send_test_request(method, proxy, judge):
    resp, content, err = None, None, None
    request, rv = _request(
        method=method,
        host=judge.host,
        path=judge.path,
        fullpath=proxy.ngtr.use_full_path,
    )
    try:
        await proxy.send(request)
        resp = await proxy.recv()
        code = get_status_code(resp)
        if code != 200:
            err = BadStatusError
            raise err
        headers, content, *_ = resp.split(b'\r\n\r\n', maxsplit=1)
    except ValueError:
        err = BadResponseError
        raise err
    finally:
        proxy.log('Get: %s' % ('success' if content else 'failed'), err=err)
        log.debug(
            '{h}:{p} [{n}]: ({j}) rv: {rv}, response: {resp}'.format(
                h=proxy.host,
                p=proxy.port,
                n=proxy.ngtr.name,
                j=judge.url,
                rv=rv,
                resp=resp,
            )
        )
    return headers, content, rv


def _decompress_content(headers, content):
    headers = parse_headers(headers)
    is_compressed = headers.get('Content-Encoding') in ('gzip', 'deflate')
    is_chunked = headers.get('Transfer-Encoding') == 'chunked'
    if is_compressed:
        # gzip: zlib.MAX_WBITS|16;
        # deflate: -zlib.MAX_WBITS;
        # auto: zlib.MAX_WBITS|32;
        if is_chunked:
            # b'278\r\n\x1f\x8b...\x00\r\n0\r\n\r\n' => b'\x1f\x8b...\x00
            content = b''.join(content.split(b'\r\n')[1::2])
        try:
            content = zlib.decompress(content, zlib.MAX_WBITS | 32)
        except zlib.error:
            content = b''
    return content.decode('utf-8', 'ignore')


def _check_test_response(proxy, headers, content, rv):
    verIsCorrect = rv in content
    refSupported = get_headers()['Referer'] in content
    cookieSupported = get_headers()['Cookie'] in content
    foundIP = get_all_ip(content)

    if all([verIsCorrect, foundIP, refSupported, cookieSupported]):
        proxy.log('Response: correct')
        return True
    else:
        proxy.log(
            'Response: not correct; ip: %s, rv: %s, ref: %s, cookie: %s'
            % (bool(foundIP), verIsCorrect, refSupported, cookieSupported)
        )
        return False


def _get_anonymity_lvl(real_ext_ip, proxy, judge, content):
    content = content.lower()
    foundIP = get_all_ip(content)

    via = (content.count('via') > judge.marks['via']) or (
        content.count('proxy') > judge.marks['proxy']
    )

    if real_ext_ip in foundIP:
        lvl = 'Transparent'
    elif via:
        lvl = 'Anonymous'
    else:
        lvl = 'High'
    proxy.log('A: {lvl}; {ip}; via(p): {via}'.format(lvl=lvl[:4], ip=foundIP, via=via))
    return lvl


class ProxyChecker(Checker):
    def __init__(self, *args, **kwargs):
        warnings.warn(
            '`ProxyChecker` is deprecated, use `Checker` instead.',
            DeprecationWarning,
        )
        super().__init__(*args, **kwargs)
