import asyncio
import random
from urllib.parse import urlparse

import aiohttp

from .errors import ResolveError
from .resolver import Resolver
from .utils import get_headers, log


class Judge:
    """Proxy Judge."""

    available = {'HTTP': [], 'HTTPS': [], 'SMTP': []}
    ev = {
        'HTTP': asyncio.Event(),
        'HTTPS': asyncio.Event(),
        'SMTP': asyncio.Event(),
    }

    def __init__(self, url, timeout=8, verify_ssl=False, loop=None):
        self.url = url
        self.scheme = urlparse(url).scheme.upper()
        self.host = urlparse(url).netloc
        self.path = url.split(self.host)[-1]
        self.ip = None
        self.is_working = False
        self.marks = {'via': 0, 'proxy': 0}
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._loop = loop or asyncio.get_event_loop()
        self._resolver = Resolver(loop=self._loop)

    def __repr__(self):
        """Class representation"""
        return '<Judge [%s] %s>' % (self.scheme, self.host)

    @classmethod
    def get_random(cls, proto):
        if proto == 'HTTPS':
            scheme = 'HTTPS'
        elif proto == 'CONNECT:25':
            scheme = 'SMTP'
        else:
            scheme = 'HTTP'
        return random.choice(cls.available[scheme])

    @classmethod
    def clear(cls):
        cls.available['HTTP'].clear()
        cls.available['HTTPS'].clear()
        cls.available['SMTP'].clear()
        cls.ev['HTTP'].clear()
        cls.ev['HTTPS'].clear()
        cls.ev['SMTP'].clear()

    async def check(self, real_ext_ip):
        # TODO: need refactoring
        try:
            self.ip = await self._resolver.resolve(self.host)
        except ResolveError:
            return

        if self.scheme == 'SMTP':
            self.is_working = True
            self.available[self.scheme].append(self)
            self.ev[self.scheme].set()
            return

        page = False
        headers, rv = get_headers(rv=True)
        connector = aiohttp.TCPConnector(
            loop=self._loop, ssl=self.verify_ssl, force_close=True
        )
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(
                connector=connector, timeout=timeout, loop=self._loop
            ) as session, session.get(
                url=self.url, headers=headers, allow_redirects=False
            ) as resp:
                page = await resp.text()
        except (
            asyncio.TimeoutError,
            aiohttp.ClientOSError,
            aiohttp.ClientResponseError,
            aiohttp.ServerDisconnectedError,
        ) as e:
            log.debug('%s is failed. Error: %r;' % (self, e))
            return

        page = page.lower()

        if resp.status == 200 and real_ext_ip in page and rv in page:
            self.marks['via'] = page.count('via')
            self.marks['proxy'] = page.count('proxy')
            self.is_working = True
            self.available[self.scheme].append(self)
            self.ev[self.scheme].set()
            log.debug('%s is verified' % self)
        else:
            log.debug(
                (
                    '{j} is failed. HTTP status code: {code}; '
                    'Real IP on page: {ip}; Version: {word}; '
                    'Response: {page}'
                ).format(
                    j=self,
                    code=resp.status,
                    page=page,
                    ip=(real_ext_ip in page),
                    word=(rv in page),
                )
            )


def get_judges(judges=None, timeout=8, verify_ssl=False):
    judges = judges or [
        'http://httpbin.org/get?show_env',
        'https://httpbin.org/get?show_env',
        'smtp://smtp.gmail.com',
        'smtp://aspmx.l.google.com',
        'http://azenv.net/',
        'https://www.proxy-listen.de/azenv.php',
        'http://www.proxyfire.net/fastenv',
        'http://proxyjudge.us/azenv.php',
        'http://ip.spys.ru/',
        'http://www.proxy-listen.de/azenv.php',
    ]
    _judges = []
    for j in judges:
        j = j if isinstance(j, Judge) else Judge(j)
        j.timeout = timeout
        j.verify_ssl = verify_ssl
        _judges.append(j)
    return _judges
