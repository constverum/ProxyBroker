import socket
import urllib
import asyncio
import logging
from functools import partial

log = logging.getLogger(__package__)

class Judge:
    loop = asyncio.get_event_loop()
    myRealIP = None
    timeout = 0

    def __init__(self, url):
        self.url = url
        self.host = urllib.parse.urlparse(url).netloc
        log.debug('%s: %s' % (self.host, type(self.host)))
        self.path = url.split(self.host)[-1]
        self.ip = None
        self.bip = None
        self.isWorking = None

    async def set_ip(self):
        log.debug('%s: set_ip' % self.host)
        try:
            self.ip = await asyncio.wait_for(
                             self.loop.run_in_executor(
                              None, socket.gethostbyname, self.host),
                             self.timeout/2)
        except (socket.gaierror, asyncio.TimeoutError) as e:
            log.debug('\n\n\n%s: set_ip ERROR: %s' % (self.host, e))
            self.isWorking = False
            return
        # print('%s: set_ip ip: %s' % (self.host, self.ip))
        self.bip = socket.inet_aton(self.ip)
        # print('%s: set_ip bip: %s' % (self.host, self.bip))

    async def check_response(self):
        # log.debug('%s: check_response; timeout: %d' % (self.host, self.timeout))
        try:
            log.debug('%s: request.urlopen;' % self.host)
            resp = await asyncio.wait_for(
                    self.loop.run_in_executor(
                            None, partial(urllib.request.urlopen, url=self.url, timeout=self.timeout)),
                    self.timeout)
            # resp = await self.loop.run_in_executor(
            #                 None,
            #                 partial(urllib.request.urlopen,
            #                         url=self.url,
            #                         timeout=1))
            # resp = await aiohttp.request('GET', self.url)
            # data = await resp.read()
            # data = data.lower()
        # except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout) as e:  # asyncio.TimeoutError
        except (urllib.error.HTTPError, asyncio.TimeoutError) as e:  #  urllib.error.URLError, socket.timeout
            log.debug('\n\n\n%s: check_response ERROR: %s' % (self.host, e))
            # return
        else:
            log.debug('%s: check_response STATUS: %s' % (self.host, resp.status))
            if self.isWorking is None and resp.status == 200:
                self.isWorking = True if self.myRealIP in resp.read().lower() else False

    def __repr__(self):
        return '<Judge {host}>'.format(host=self.host)
