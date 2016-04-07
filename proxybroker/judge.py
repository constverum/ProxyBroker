import random
import asyncio
from socket import inet_aton
from urllib.parse import urlparse

import aiohttp

from .utils import log, get_my_ip, get_headers, resolve_host


class Judge:
    _sem = None
    _loop = None
    _timeout = None
    _verifySSL = False
    allJudges = {'HTTP': [], 'HTTPS': []}
    ev = {'HTTP': asyncio.Event(loop=_loop),
          'HTTPS': asyncio.Event(loop=_loop)}

    def __init__(self, url):
        self.url = url
        self.scheme = urlparse(url).scheme.upper()
        self.host = urlparse(url).netloc
        self.path = url.split(self.host)[-1]
        self.ip = None
        self.bip = None
        self.isWorking = None
        self.marks = {'via': 0, 'proxy': 0}

    def __repr__(self):
        return '<Judge [%s] %s>' % (self.scheme, self.host)

    @classmethod
    def get_random(cls, scheme):
        # log.debug('SCHEME: %s::: %s' % (scheme, cls.allJudges[scheme]))
        return random.choice(cls.allJudges[scheme])

    @classmethod
    def clear(cls):
        cls.allJudges['HTTP'].clear()
        cls.allJudges['HTTPS'].clear()
        cls.ev['HTTP'].clear()
        cls.ev['HTTPS'].clear()

    async def check(self):
        await self._resolve_host()
        if self.isWorking is False:
            return
        # log.debug('%s: check_response;' % self.host)
        self.isWorking = False
        page = False
        headers, rv = get_headers(rv=True)
        connector = aiohttp.TCPConnector(
            loop=self._loop, verify_ssl=self._verifySSL, force_close=True)
        try:
            with (await self._sem),\
                 aiohttp.Timeout(self._timeout, loop=self._loop),\
                 aiohttp.ClientSession(connector=connector,
                                       loop=self._loop) as session:
                async with session.get(url=self.url, headers=headers,
                                       allow_redirects=False) as resp:
                    page = await resp.text()
        except (asyncio.TimeoutError, aiohttp.ClientOSError,
                aiohttp.ClientResponseError, aiohttp.ServerDisconnectedError) as e:
            log.error('%s is failed. Error: %r;' % (self, e))
            return

        page = page.lower()

        if (resp.status == 200 and get_my_ip() in page and rv in page):
            self.marks['via'] = page.count('via')
            self.marks['proxy'] = page.count('proxy')
            self.isWorking = True
            self.allJudges[self.scheme].append(self)
            self.ev[self.scheme].set()
            # log.debug('%s is set' % self.scheme)
            log.debug('%s is verified' % self)
        else:
            log.error(('{j} is failed. HTTP status code: {code}; '
                       'Real IP on page: {ip}; Version: {word}; '
                       'Response: {page}').format(
                      j=self, code=resp.status, page=page[0],
                      ip=(get_my_ip() in page), word=(rv in page)))

    async def _resolve_host(self):
        with (await self._sem):
            host = await resolve_host(self.host, self._timeout, self._loop)
        if host:
            self.ip = host
            self.bip = inet_aton(self.ip)
            log.debug('%s: Host resolved' % self.host)
        else:
            self.isWorking = False
            log.warning('%s: Could not resolve host' % self.host)

judgesList = [
    Judge('https://httpheader.net/'),
    Judge('https://www.proxy-listen.de/azenv.php'),
    Judge('http://httpheader.net/'),
    Judge('http://azenv.net/'),
    Judge('http://ip.spys.ru/'),
    Judge('http://proxyjudge.us/azenv.php'),
    Judge('http://www.proxyfire.net/fastenv'),
    Judge('http://www.ingosander.net/azenv.php'),
    Judge('http://www.proxy-listen.de/azenv.php'),
    ]



# def get_judges(path=None):
#     path = path or get_path_to_def_judges()
#     judges = []
#     with open(path) as f:
#         for url in f.readlines():
#             url = url.strip()
#             if not url or url.startswith('#'):
#                 continue
#             judges.append(Judge(url))
#     return judges
