import re
import asyncio
from math import sqrt
from html import unescape
from pprint import pprint
from base64 import b64decode
from urllib.parse import unquote, urlparse

import aiohttp

from .errors import *
from .utils import log, get_path_to_def_providers,\
                   get_headers, IPPattern, IPPortPatternGlobal


class ProxyProvider:
    _sem = None
    _loop = None
    _timeout = 20
    _pattern = IPPortPatternGlobal
    _attemptsConnect = 3

    def __init__(self, url=None, proto=(), max_conn=4):
        if not proto:
            sep = '|'
            _type = ()
            if url and sep in url:
                proto, url = url.split(sep)
        if url:
            self.domain = urlparse(url).netloc
        self.url = url
        self._proxies = set()
        if isinstance(proto, str):
            proto = tuple(proto.split(','))
        self.proto = proto
        # 4 concurrent connections on provider
        self._sem_provider = asyncio.Semaphore(max_conn)
        self._cookies = {}

    @property
    def proxies(self):
        return self._proxies

    @proxies.setter
    def proxies(self, new):
        new = [(host, port, self.proto) for host, port in new if port]
        self._proxies.update(new)

    async def get_proxies(self):
        await self._pipe()
        log.info('%d proxies received from %s' % (
                 len(self.proxies), self.domain))
        return self.proxies

    async def _pipe(self):
        await self._find_on_page(self.url)

    async def _find_on_pages(self, urls):
        if not urls:
            return
        tasks = []
        if not isinstance(urls[0], dict):
            urls = set(urls)
        for url in urls:
            if isinstance(url, dict):
                tasks.append(self._find_on_page(**url))
            else:
                tasks.append(self._find_on_page(url))
        await asyncio.gather(*tasks)

    async def _find_on_page(self, url, data=None, headers={},
                            cookies={}, method='GET'):
        page = await self.get(url, data=data, headers=headers,
                              cookies=cookies, method=method)
        oldcount = len(self.proxies)
        try:
            received = self.find_proxies(page)
        except Exception as e:
            received = []
            log.error('Error when executing find_proxies.'
                      'Domain: %s; Error: %s' % (self.domain, e))
        self.proxies = received
        added = len(self.proxies)-oldcount
        log.debug('%d(%d) proxies added(received) from %s' % (
            added, len(received), url))

    async def get(self, url, data=None, headers={}, cookies={}, method='GET'):
        attempt = 0
        while attempt < self._attemptsConnect:
            attempt += 1
            page = await self._get(url, data=data, headers=headers,
                                   cookies=cookies, method=method)
            if page:
                break
        return page

    async def _get(self, url, data=None, headers={}, cookies={}, method='GET'):
        page = ''
        hdrs = {**get_headers(), **headers} or None
        cookies = {**self._cookies, **cookies} or None
        with (await self._sem), (await self._sem_provider):
            req = aiohttp.request(method, url, data=data, headers=hdrs, cookies=cookies)
            try:
                with aiohttp.Timeout(self._timeout, loop=self._loop):
                    # log.debug('prov. Try to get proxies from: %s' % url)
                    async with req as resp:
                        if resp.status == 200:
                            page = await resp.text()
                        else:
                            _page = await resp.text()
                            log.debug('Url: %s\nErr.Headers: %s\nErr.Cookies: '
                                      '%s\nErr.Page:\n%s' % (
                                      url, resp.headers, resp.cookies, _page))
                            raise BadStatusError('Status: %s' % resp.status)
            # urllib.error.HTTPError, urllib.error.URLError, socket.timeout,
            # ConnectionResetError, UnicodeEncodeError, aiohttp.ClientOSError
            except (UnicodeDecodeError, BadStatusError, asyncio.TimeoutError,
                    aiohttp.ClientOSError, aiohttp.ClientResponseError,
                    aiohttp.ServerDisconnectedError) as e:
                log.error('%s is failed. Error: %r;' % (url, e))
        return page

    def find_proxies(self, page):
        return self._find_proxies(page)

    def _find_proxies(self, page):
        proxies = self._pattern.findall(page)
        return proxies

class Hitsozler_com(ProxyProvider):
    domain = 'hitsozler.com'
    _timeout = 60
    async def _pipe(self):
        await self._find_on_page('http://hitsozler.com/')

class Freeproxylists_com(ProxyProvider):
    domain = 'freeproxylists.com'
    async def _pipe(self):
        exp = r'''href\s*=\s*['"](?P<t>[^'"]*)/(?P<uts>\d{10})[^'"]*['"]'''
        urls = ['http://www.freeproxylists.com/socks.html',
                'http://www.freeproxylists.com/elite.html',
                'http://www.freeproxylists.com/anonymous.html']
        pages = await asyncio.gather(*[self.get(url) for url in urls])
        params = re.findall(exp, ''.join(pages))
        tpl = 'http://www.freeproxylists.com/load_{}_{}.html'
        # example: http://www.freeproxylists.com/load_socks_1448724717.html
        urls = [tpl.format(t, uts) for t, uts in params]
        await self._find_on_pages(urls)

class Any_blogspot_com(ProxyProvider):
    domain = 'blogspot.com'
    async def _pipe(self):
        self._cookies = {'NCR': 1}
        exp = r'''<a href\s*=\s*['"]([^'"]*\.\w+/\d{4}/\d{2}/[^'"#]*)['"]>'''
        domains = ['proxyserverlist-24.blogspot.com', 'newfreshproxies24.blogspot.com',
                   'irc-proxies24.blogspot.com', 'googleproxies24.blogspot.com',
                   'elitesocksproxy.blogspot.com', 'www.proxyocean.com',
                   'www.socks24.org']
        pages = await asyncio.gather(*[
                        self.get('http://%s/' % d) for d in domains])
        urls = re.findall(exp, ''.join(pages))
        await self._find_on_pages(urls)


class Webanetlabs_net(ProxyProvider):
    domain = 'webanetlabs.net'
    async def _pipe(self):
        exp = r'''href\s*=\s*['"]([^'"]*proxylist_at_[^'"]*)['"]'''
        page = await self.get('http://webanetlabs.net/publ/24')
        urls = ['http://webanetlabs.net%s' % path
                 for path in re.findall(exp, page)]
        await self._find_on_pages(urls)


class Checkerproxy_net(ProxyProvider):
    domain = 'checkerproxy.net'
    async def _pipe(self):
        exp = r'''href\s*=\s*['"]([^'"]?\d{2}-\d{2}-\d{4}[^'"]*)['"]'''
        page = await self.get('http://checkerproxy.net/')
        urls = ['http://checkerproxy.net%s' % path
                 for path in re.findall(exp, page)]
        await self._find_on_pages(urls)


class Proxz_com(ProxyProvider):
    domain = 'proxz.com'
    def find_proxies(self, page):
        return self._find_proxies(unquote(page))

    async def _pipe(self):
        exp = r'''href\s*=\s*['"]([^'"]?proxy_list_high_anonymous_[^'"]*)['"]'''
        url = 'http://www.proxz.com/proxy_list_high_anonymous_0.html'
        page = await self.get(url)
        urls = ['http://www.proxz.com/%s' % path
                 for path in re.findall(exp, page)]
        urls.append(url)
        await self._find_on_pages(urls)


class Proxy_list_org(ProxyProvider):
    domain = 'proxy-list.org'
    _pattern = re.compile(r'''Proxy\('([\w=]+)'\)''')
    def find_proxies(self, page):
        return [b64decode(hp).decode().split(':')
                for hp in self._find_proxies(page)]

    async def _pipe(self):
        exp = r'''href\s*=\s*['"]\./([^'"]?index\.php\?p=\d+[^'"]*)['"]'''
        url = 'http://proxy-list.org/english/index.php?p=1'
        page = await self.get(url)
        urls = ['http://proxy-list.org/english/%s' % path
                 for path in re.findall(exp, page)]
        urls.append(url)
        await self._find_on_pages(urls)


class Aliveproxy_com(ProxyProvider):
    # more: http://www.aliveproxy.com/socks-list/socks5.aspx/United_States-us
    domain = 'aliveproxy.com'
    async def _pipe(self):
        paths = [
        'socks5-list', 'high-anonymity-proxy-list', 'anonymous-proxy-list',
        'fastest-proxies', 'us-proxy-list', 'gb-proxy-list', 'fr-proxy-list',
        'de-proxy-list', 'jp-proxy-list', 'ca-proxy-list', 'ru-proxy-list',
        'proxy-list-port-80', 'proxy-list-port-81', 'proxy-list-port-3128',
        'proxy-list-port-8000', 'proxy-list-port-8080']
        urls = ['http://www.aliveproxy.com/%s/' % path for path in paths]
        await self._find_on_pages(urls)


class Maxiproxies_com(ProxyProvider):
    domain = 'maxiproxies.com'
    async def _pipe(self):
        exp = r'''<a href\s*=\s*['"]([^'"]*example[^'"#]*)['"]>'''
        page = await self.get('http://maxiproxies.com/category/proxy-lists/')
        urls = re.findall(exp, page)
        await self._find_on_pages(urls)


class _50kproxies_com(ProxyProvider):
    domain = '50kproxies.com'
    _timeout = 20
    async def _pipe(self):
        exp = r'''<a href\s*=\s*['"]([^'"]*-proxy-list-[^'"#]*)['"]>'''
        page = await self.get('http://50kproxies.com/category/proxy-list/')
        urls = re.findall(exp, page)
        await self._find_on_pages(urls)


class Proxymore_com(ProxyProvider):
    domain = 'proxymore.com'
    async def _pipe(self):
        urls = ['http://www.proxymore.com/proxy-list-%d.html' % n
                for n in range(1, 56)]
        await self._find_on_pages(urls)


class Proxylist_me(ProxyProvider):
    domain = 'proxylist.me'
    async def _pipe(self):
        exp = r'''href\s*=\s*['"][^'"]*/proxys/index/(\d+)['"]'''
        page = await self.get('http://proxylist.me/')
        lastId = max([int(n) for n in re.findall(exp, page)])
        urls = ['http://proxylist.me/proxys/index/%d' %
                n for n in range(lastId, -20, -20)]
        await self._find_on_pages(urls)


class Foxtools_ru(ProxyProvider):
    domain = 'foxtools.ru'
    async def _pipe(self):
        urls = ['http://api.foxtools.ru/v2/Proxy.txt?page=%d' % n
                for n in range(1, 6)]
        await self._find_on_pages(urls)


class Gatherproxy_com(ProxyProvider):
    domain = 'gatherproxy.com'
    _pattern_h = re.compile(
        r'''(?P<ip>(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?))'''
        r'''(?=.*?(?:(?:(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?))|'(?P<port>[\d\w]+)'))''',
        flags=re.DOTALL)
    def find_proxies(self, page):
        if 'gp.dep' in page:
            proxies = self._pattern_h.findall(page)  # for http(s)
            proxies = [(host, str(int(port, 16))) for host, port in proxies if port]
        else:
            proxies = self._find_proxies(page)  # for socks
        return proxies

    async def _pipe(self):
        url = 'http://www.gatherproxy.com/proxylist/anonymity/'
        expNumPages = r'href="#(\d+)"'
        method = 'POST'
        # hdrs = {'Content-Type': 'application/x-www-form-urlencoded'}
        urls = []
        for t in ['anonymous', 'elite']:
            data = {'Type': t, 'PageIdx': 1}
            page = await self.get(url, data=data, method=method)
            if not page:
                continue
            lastPageId = max([int(n) for n in re.findall(expNumPages, page)])
            urls = [{'url': url, 'data': {'Type': t, 'PageIdx': pid},
                     'method': method} for pid in range(1, lastPageId+1)]
        urls.append({'url': 'http://www.gatherproxy.com/sockslist/',
                     'method': method})
        await self._find_on_pages(urls)


class Tools_rosinstrument_com(ProxyProvider):
    # more
    # http://tools.rosinstrument.com/cgi-bin/sps.pl?pattern=month-1&max=50&nskip=0&file=proxlog.csv
    domain = 'tools.rosinstrument.com'
    sqrtPattern = re.compile(r'''sqrt\((\d+)\)''')
    bodyPattern = re.compile(r'''hideTxt\(\n*'(.*)'\);''')
    _pattern = re.compile(
        r'''(?:(?P<domainOrIP>(?:[a-z0-9\-.]+\.[a-z]{2,6})|'''
        r'''(?:(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}'''
        r'''(?:25[0-5]|2[0-4]\d|[01]?\d\d?))))(?=.*?(?:(?:'''
        r'''[a-z0-9\-.]+\.[a-z]{2,6})|(?:(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)'''
        r'''\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?))|(?P<port>\d{2,5})))''',
        flags=re.DOTALL)

    def find_proxies(self, page):
        x = self.sqrtPattern.findall(page)
        if not x:
            return []
        x = round(sqrt(float(x[0])))
        hiddenBody = self.bodyPattern.findall(page)[0]
        hiddenBody = unquote(hiddenBody)
        toCharCodes = [ord(char)^(x if i%2 else 0)
                       for i, char in enumerate(hiddenBody)]
        fromCharCodes = ''.join([chr(n) for n in toCharCodes])
        page = unescape(fromCharCodes)
        return self._find_proxies(page)

    async def _pipe(self):
        tpl = 'http://tools.rosinstrument.com/raw_free_db.htm?%d&t=%d'
        urls = [tpl % (pid, t) for pid in range(51) for t in range(1, 4)]
        await self._find_on_pages(urls)


class Xseo_in(ProxyProvider):
    domain = 'xseo.in'
    charEqNum = {}
    def char_js_port_to_num(self, matchobj):
        chars = matchobj.groups()[0]
        num = ''.join([self.charEqNum[ch] for ch in chars if ch != '+'])
        return num

    def find_proxies(self, page):
        expPortOnJS = r'\(""\+(?P<chars>[a-z+]+)\)'
        expCharNum = r'\b(?P<char>[a-z])=(?P<num>\d);'
        self.charEqNum = {char: i for char, i in re.findall(expCharNum, page)}
        page = re.sub(expPortOnJS, self.char_js_port_to_num, page)
        return self._find_proxies(page)

    async def _pipe(self):
        await self._find_on_page(
            url='http://xseo.in/proxylist', data={'submit': 1}, method='POST')


class Nntime_com(ProxyProvider):
    domain = 'nntime.com'
    charEqNum = {}
    _pattern = re.compile(
        r'''\b(?P<ip>(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}'''
        r'''(?:25[0-5]|2[0-4]\d|[01]?\d\d?))(?=.*?(?:(?:(?:(?:25'''
        r'''[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)'''
        r''')|(?P<port>\d{2,5})))''',
        flags=re.DOTALL)
    def char_js_port_to_num(self, matchobj):
        chars = matchobj.groups()[0]
        num = ''.join([self.charEqNum[ch] for ch in chars if ch != '+'])
        return num

    def find_proxies(self, page):
        expPortOnJS = r'\(":"\+(?P<chars>[a-z+]+)\)'
        expCharNum = r'\b(?P<char>[a-z])=(?P<num>\d);'
        self.charEqNum = {char: i for char, i in re.findall(expCharNum, page)}
        page = re.sub(expPortOnJS, self.char_js_port_to_num, page)
        return self._find_proxies(page)

    async def _pipe(self):
        tpl = 'http://www.nntime.com/proxy-updated-{:02}.htm'
        urls = [tpl.format(n) for n in range(1, 31)]
        await self._find_on_pages(urls)


class Proxynova_com(ProxyProvider):
    domain = 'proxynova.com'
    async def _pipe(self):
        expCountries = r'"([a-z]{2})"'
        page = await self.get('http://www.proxynova.com/proxy-server-list/')
        tpl = 'http://www.proxynova.com/proxy-server-list/country-%s/'
        urls = [tpl % isoCode for isoCode in re.findall(expCountries, page)]
        await self._find_on_pages(urls)


class Spys_ru(ProxyProvider):
    domain = 'spys.ru'
    charEqNum = {}
    def char_js_port_to_num(self, matchobj):
        chars = matchobj.groups()[0].split('+')
        # ex: '+(i9w3m3^k1y5)+(g7g7g7^v2e5)+(d4r8o5^i9u1)+(y5c3e5^t0z6)'
        # => ['', '(i9w3m3^k1y5)', '(g7g7g7^v2e5)', '(d4r8o5^i9u1)', '(y5c3e5^t0z6)']
        # => ['i9w3m3', 'k1y5'] => int^int
        num = ''
        for numOfChars in chars[1:]: # first - is ''
            var1, var2 = numOfChars.strip('()').split('^')
            digit = self.charEqNum[var1]^self.charEqNum[var2]
            num += str(digit)
        return num

    def find_proxies(self, page):
        expPortOnJS = r'(?P<js_port_code>(?:\+\([a-z0-9^+]+\))+)'
        # expCharNum = r'\b(?P<char>[a-z\d]+)=(?P<num>[a-z\d\^]+);'
        expCharNum = r'[>;]{1}(?P<char>[a-z\d]{4,})=(?P<num>[a-z\d\^]+)'
        # self.charEqNum = {char: i for char, i in re.findall(expCharNum, page)}
        res = re.findall(expCharNum, page)
        for char, num in res:
            if '^' in num:
                digit, tochar = num.split('^')
                num = int(digit) ^ self.charEqNum[tochar]
            self.charEqNum[char] = int(num)
        page = re.sub(expPortOnJS, self.char_js_port_to_num, page)
        return self._find_proxies(page)

    async def _pipe(self):
        expSession = r"'([a-z0-9]{32})'"
        url = 'http://spys.ru/proxies/'
        page = await self.get(url)
        sessionId = re.findall(expSession, page)[0]
        data = {'xf0': sessionId, # session id
                'xpp': 3,         # 3 - 200 proxies on page
                'xf1': None}      # 1 = ANM & HIA; 3 = ANM; 4 = HIA
        method = 'POST'
        urls = [{'url': url, 'data': {**data, 'xf1': lvl},
                 'method': method} for lvl in [3, 4]]
        await self._find_on_pages(urls)
        # expCountries = r'>([A-Z]{2})<'
        # url = 'http://spys.ru/proxys/'
        # page = await self.get(url)
        # links = ['http://spys.ru/proxys/%s/' %
        #          isoCode for isoCode in re.findall(expCountries, page)]


class My_proxy_com(ProxyProvider):
    domain = 'my-proxy.com'
    async def _pipe(self):
        exp = r'''href\s*=\s*['"]([^'"]?free-[^'"]*)['"]'''
        url = 'http://www.my-proxy.com/free-proxy-list.html'
        page = await self.get(url)
        urls = ['http://www.my-proxy.com/%s' % path
                 for path in re.findall(exp, page)]
        urls.append(url)
        await self._find_on_pages(urls)


class Free_proxy_cz(ProxyProvider):
    domain = 'free-proxy.cz'
    _pattern = re.compile(r'''decode\("([\w=]+)".*?\("([\w=]+)"\)''',
                          flags=re.DOTALL)
    def find_proxies(self, page):
        return [(b64decode(h).decode(), b64decode(p).decode())
                for h, p in self._find_proxies(page)]

    async def _pipe(self):
        tpl = 'http://free-proxy.cz/en/proxylist/main/date/%d'
        urls = [tpl % n for n in range(1, 15)]
        await self._find_on_pages(urls)
        # _urls = []
        # for url in urls:
        #     if len(_urls) == 15:
        #         await self._find_on_pages(_urls)
        #         print('sleeping on 61 sec')
        #         await asyncio.sleep(61)
        #         _urls = []
        #     _urls.append(url)
        # =========
        # expNumPages = r'href="/en/proxylist/main/(\d+)"'
        # page = await self.get('http://free-proxy.cz/en/')
        # if not page:
        #     return
        # lastPageId = max([int(n) for n in re.findall(expNumPages, page)])
        # tpl = 'http://free-proxy.cz/en/proxylist/main/date/%d'
        # urls = [tpl % pid for pid in range(1, lastPageId+1)]
        # _urls = []
        # for url in urls:
        #     if len(_urls) == 15:
        #         await self._find_on_pages(_urls)
        #         print('sleeping on 61 sec')
        #         await asyncio.sleep(61)
        #         _urls = []
        #     _urls.append(url)

class Proxyb_net(ProxyProvider):
    domain = 'proxyb.net'
    _port_pattern_b64 = re.compile(r"stats\('([\w=]+)'\)")
    _port_pattern = re.compile(r"':(\d+)'")
    def find_proxies(self, page):
        if not page:
            return []
        _hosts, _ports = page.split('","ports":"')
        hosts, ports = [], []
        for host in _hosts.split('<\/tr><tr>'):
            host = IPPattern.findall(host)
            if not host:
                continue
            hosts.append(host[0])
        ports = [self._port_pattern.findall(b64decode(port).decode())[0]
                 for port in self._port_pattern_b64.findall(_ports)]
        return [(host, port) for host, port in zip(hosts, ports)]

    async def _pipe(self):
        url = 'http://proxyb.net/ajax.php'
        method = 'POST'
        data = {'action': 'getProxy', 'p': 0,
                'page': '/anonimnye_proksi_besplatno.html'}
        hdrs = {'X-Requested-With': 'XMLHttpRequest'}
        urls = [{'url': url, 'data': {**data, 'p': p},
                 'method': method, 'headers': hdrs} for p in range(0, 151)]
        await self._find_on_pages(urls)


extProviders = [
    Proxy_list_org(proto=('HTTP', 'HTTPS')),                  # 140/87 HTTP(S)
    Xseo_in(proto=('HTTP', 'HTTPS')),                         # 252/113 HTTP(S)
    Spys_ru(proto=('HTTP', 'HTTPS')),                         # 693/238 HTTP(S)
    Aliveproxy_com(),                                         # 210/63 SOCKS(~10)/HTTP(S)
    Proxyb_net(),                                             # 4309/4113 SOCKS(~11)
    Hitsozler_com(proto=('HTTP', 'HTTPS')),                   # 13546/6463
    Freeproxylists_com(),                                     # 6094/4203 SOCKS/HTTP(S)
    Any_blogspot_com(),                                       # 4471/2178 ... 8234/
    Webanetlabs_net(),                                        # 2737/700
    Checkerproxy_net(),                                       # 8382/1279 SOCKS(~30)/HTTP(S)
    Proxz_com(proto=('HTTP', 'HTTPS'), max_conn=2),           # 3800/3486 HTTP(S)
    Maxiproxies_com(),                                        # 626/169 SOCKS(~15)/HTTP(S)
    _50kproxies_com(),                                        # 934/218 SOCKS(~38)/HTTP(S)
    Proxymore_com(proto=('HTTP', 'HTTPS')),                   # 1356/780
    Proxylist_me(proto=('HTTP', 'HTTPS')),                    # 1078/587
    Foxtools_ru(proto=('HTTP', 'HTTPS'), max_conn=1),         # 500/187 HTTP(S)
    Gatherproxy_com(),                                        # 2524/1264 SOCKS/HTTP(S)
    Tools_rosinstrument_com(),                                # 7142/2367 SOCKS(~30)/HTTP(S)
    Nntime_com(proto=('HTTP', 'HTTPS')),                      # 1050/582 HTTP(S)
    Proxynova_com(proto=('HTTP', 'HTTPS')),                   # 1229/878 HTTP(S)
    My_proxy_com(max_conn=2),                                 # 894/408 SOCKS(~10)/HTTP(S)
    Free_proxy_cz(),                                          # 330/195 SOCKS(~2)
]


def get_providers(path=None):
    _path = path or get_path_to_def_providers()
    providers = []
    with open(_path) as f:
        for url in f.readlines():
            url = url.strip()
            if not url or url.startswith('#'):
                continue
            providers.append(ProxyProvider(url))
    if not path:
        providers.extend(extProviders)
        log.debug('providers: %s' % providers)
    return providers
