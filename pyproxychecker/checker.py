"""
Copyright © 2015 Constverum <constverum@gmail.com>. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import re
import sys
import ssl
import time
import json
import socket
import struct
import aiohttp
import asyncio
import logging
import pprint
import random
import urllib.request
from collections import defaultdict, Counter, Iterable

from .errors import *
from .proxy import Proxy
from .judge import Judge
from .utils import connector, mmdbSrc
from .negotiators import *

log = logging.getLogger(__package__)


class ProxyChecker:
    def __init__(self,
                 proxies=[],
                 timeout=6,
                 connects=3,
                 sslverify=False,
                 judges=[],
                 getgeo=True):  # dest=None, **kwargs
        if not proxies:
            raise ValueError('You must set proxy list in <proxies> var')
        if not isinstance(judges, Iterable):
            raise ValueError('<judges> var must be a iterable type of urls')

        self.proxies = dict(input=proxies, clean=[], good=[], bad=[])
        # self.ngtrs = dict(HTTP=HttpNgtr, HTTPS=HttpsNgtr, CONNECT=ConnectNgtr,
        #                   SOCKS4=Socks4Ngtr, SOCKS5=Socks5Ngtr)
        self.ngtrs = dict(HTTP=HttpNgtr(), HTTPS=HttpsNgtr(), CONNECT=ConnectNgtr(),
                          SOCKS4=Socks4Ngtr(), SOCKS5=Socks5Ngtr())
        self.getgeo = getgeo
        self.judges = judges
        Judge.timeout = timeout
        Proxy.timeout = timeout
        BaseNegotiator.timeout = timeout
        BaseNegotiator.attemptsConnect = connects
        BaseNegotiator.sslContext = sslverify or ssl._create_unverified_context()
        self.countries = []
        # self.timeout = timeout  # in seconds
        # self.sslContext = True if sslverify else ssl._create_unverified_context()
        # self.attemptsConnect = connects

        # self.dest = {'host': 'httpbin.org',
        #                      'port': 80,
        #                      'page': '/get?show_env',
        #                      'length': -1,
        #                      'search': 'headers'}
        # addr = socket.inet_aton(
        #            socket.gethostbyname(
        #                self.dest['host']))  # b'J}\x8fj'
        # defua = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:41.0)'\
        #         'Gecko/20100101 Firefox/41.0'

        # self.requests = dict(
        #     SOCKS4=struct.pack('>2BH5B', 4, 1, 80, *bip, 0),
        #     SOCKS5=[struct.pack('3B', 5, 1, 0),
        #             struct.pack('>8BH', 5, 1, 0, 1, *bip, 80)],
        #     CONNECT='CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}\r\n'
        #             'Connection: keep-alive\r\n\r\n'.format(
        #                 host=self.dest['host'], port=443).encode(),
        #     GET='GET {page} HTTP/1.1\r\nHost: {host}\r\nAccept: *.*, */*\r\nConnection: close\r\n\r\n')

        # self.ngtrs = [
        #     {'name': 'SOCKS4', 'fn': self.negotiate_SOCKS4},
        #     {'name': 'HTTP', 'fn': self.negotiate_HTTP},
        #     {'name': 'SOCKS5', 'fn': self.negotiate_SOCKS5},
        #     {'name': 'HTTPS', 'fn': self.negotiate_HTTPS}]

    def start(self):
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.run())
        self.loop.close()

    async def run(self):
        myRealIP = self.get_my_ip()
        Judge.myRealIP = myRealIP
        Proxy.myRealIP = myRealIP

        await self.check_judges()
        await self.clear_proxies()

        stime = time.time()

        # await asyncio.wait([self.check_proxy(p) for p in proxies])
        await asyncio.gather(*[
            asyncio.ensure_future(self.check_proxy(p))
            for p in self.proxies['clean']])

        log.info('Complete: %.2f sec', time.time()-stime)

        # self.tasks = asyncio.Queue()
        # for p in self.proxies['input']:
        #     self.tasks.put(asyncio.ensure_future(self.check_proxy(p)))
        #     log.debug('Check %d proxies', self.tasks.qsize())
        # while True:
        #     task = await self.tasks.get()
        #     print('task:', task)
        #     await task

    # def get_host_by_name(self, name):
    #         return self.loop.run_in_executor(
    #                 None, socket.gethostbyname, name)

    def show_stats(self):
        if not self.getgeo:
            return False
        count = defaultdict(Counter)
        for p in self.get_proxies():
            country = '{iso}: {name:<20}'.format(
                iso=p.geo.get('iso_code', 'Unknown'),
                name=p.geo.get('names', {}).get('en', 'Unknown'))
            for tp, lvl in p.types.items():
                tplvl = '{type}: {lvl}'.format(type=tp, lvl=lvl)
                count[country][tplvl] += 1

        stat = {country: tplvls for country, tplvls in count.items()}
        # stat['Number of live proxies'] = len(self.get_proxies())
        # stat['HTTP'] = len(self.get_proxies('HTTP'))
        # stat['HTTPS'] = len(self.get_proxies('HTTPS'))
        # stat['CONNECT'] = len(self.get_proxies('CONNECT'))
        # stat['SOCKS4'] = len(self.get_proxies('SOCKS4'))
        # stat['SOCKS5'] = len(self.get_proxies('SOCKS5'))
        return stat

    async def check_judges(self):
        log.debug('Start check judges')
        stime = time.time()
        judges = [Judge(url=url) for url in self.judges]

        await asyncio.gather(*(asyncio.ensure_future(j.set_ip())
                             for j in judges))
        await asyncio.gather(*(asyncio.ensure_future(
            j.check_response()) for j in judges))

        self.judges = [j for j in judges if j.isWorking]

        log.info('End check judges. Runtime: %.4f;\nJudges: %s' % (
            time.time()-stime, self.judges))

    async def clear_proxies(self):
        proxies = [Proxy(*p, judge=random.choice(self.judges))
                   for p in self.proxies['input']]

        # Remove duplicates
        proxies = await asyncio.gather(*[
            asyncio.ensure_future(
                self.resolve_host(p))
            for p in proxies])
        self.proxies['clean'] = {p.host: p for p in proxies if p}.values()

        log.info('Stat: Received: %d / Unique: %d',
                  len(self.proxies['input']), len(self.proxies['clean']))

    async def resolve_host(self, p):
        name = p.host
        stime = time.time()
        try:
            p.host = await self.loop.run_in_executor(
                            None, socket.gethostbyname, p.host)
            msg = 'Host resolved (orig. name: %s)' % name
        except socket.gaierror:
            msg = 'Could not resolve host'
            return None
        else:
            return p
        finally:
            p.log(msg, stime)

    def get_proxies(self, types=[], country=None):
        # TODO: rewrite this shit
        def check_types(types):
            _types = []
            if isinstance(types, str):             # ex: 'HTTPS:High'
                _types.append(types.split(':'))
            elif isinstance(types, (list, tuple)): # ex: ['HTTP:High', 'SOCKS5']
                _types.extend([t.split(':') for t in types])
            else:
                raise ValueError('To get proxies preferred type use format: '
                                 '"HTTP:High" or if you you need multiple '
                                 'types: ["HTTP:Anonymous", "HTTPS"]')
            types = {t[0]: t[1] if len(t) == 2 else '' for t in _types}
            return types

        def check_country(country):
            if isinstance(country, str):
                country = country.split(',')
            elif isinstance(country, (list, tuple)):
                pass
            else:
                raise ValueError('To get proxies preferred country use format: '
                                 '"US" or if you you need a few countries: '
                                 '["US", "GB", "DE"])')
            return set(c for c in country if len(c) == 2)

        if not (types or country):
            return self.proxies['good']

        if types:
            types = check_types(types)
            # print('types after check: %s' % types)
        if country:
            country = check_country(country)
            # print('country after check: %s' % country)

        res = []
        aLvlIsOk = lambda types, p: any(tp == _tp and (not lvl or lvl == _lvl)
                for tp, lvl in types.items() for _tp, _lvl in p.types.items())

        # (types.keys() & p.types.keys()) and\
        for p in self.proxies['good']:
            # print('\n\n', p)
            if (not types or aLvlIsOk(types, p)) and\
               (not country or p.geo.get('iso_code') in country):
                # print('not types: %s; aLvlIsOk(types, p): %s' % (not types, aLvlIsOk(types, p)))
                # print('(not types or aLvlIsOk(types, p)): %s' % (not types or aLvlIsOk(types, p)))
                # print('not country: %s; p.geo.get(iso_code) in country: %s' % (not country, (p.geo.get('iso_code') in country) if country else '::not country::'))
                # print('(not country or p.geo.get(iso_code) in country): %s' % (not country or p.geo.get('iso_code') in country))

                res.append(p)
            # elif types and aLvlIsOk(types, p):
            #     res.append(p)
            # elif country and (p.geo.get('iso_code') in country):
            #     res.append(p)
            else:
                pass
                # print('\n\nIF:::\ncount: %s; types: %s; country: %s\nProxy: %s' % (count, types, country, p))
                # raise Exception('WTF?')

        return res

    def get_my_ip(self):
        # TODO: add try/except
        url = 'http://httpbin.org/get?show_env'
        data = urllib.request.urlopen(url)
        data = json.loads(data.read().decode())
        ip = data['origin']
        headers = data['headers']
        log.debug('IP: %s;\nHeaders: %s;' % (ip, headers))
        return ip.encode()

    async def check_proxy(self, p):
        if p._types:
            # ngtrs = [n for n in self.ngtrs if n['name'] in p.types]
            ngtrs = [self.ngtrs[n] for n in p._types]
        else:
            ngtrs = self.ngtrs.values()
            # ngtrs = self.ngtrs[:]
            # ngtrs = ['HTTP', 'HTTPS', 'SOCKS4', 'SOCKS5']
            # ngtrs = list(_ngtrs.values())
            # ngtrs = [{'name': 'HTTP', 'fn': self.negotiate_HTTP}]
            # ngtrs = [
            #     {'name': 'HTTP', 'fn': HttpNgtr},
            #     {'name': 'HTTPS', 'fn': HttpsNgtr},
            #     {'name': 'CONNECT', 'fn': ConnectNgtr},
            #     {'name': 'SOCKS4', 'fn': Socks4Ngtr},
            #     {'name': 'SOCKS5', 'fn': Socks5Ngtr},
            # ]

# HTTPS: если разрешен CONNECT к порту 443 (https:// адреса)
# CONNECT: если разрешен CONNECT к любым портам (не считая 443 и 25)

        results = await asyncio.gather(*[
            asyncio.ensure_future(n(p=p.get_descendant(ngtr=n)))
            for n in ngtrs])
        p.isWorking = True if any(results) else False

        if p.isWorking:
            if self.getgeo:
                p.set_geo()
            p.set_avg_resp_time()
            self.proxies['good'].append(p)
        else:
            self.proxies['bad'].append(p)

            # p.reader, p.writer = await asyncio.wait_for(
            #         asyncio.open_connection(p.host, p.port),
            #         timeout=self.timeout)

        # results = await asyncio.gather(*[
        #             asyncio.ensure_future(
        #               n['fn'](p=Proxy(p.host, p.port, ngtr=n['name'], judge=p.judge), sem=None))
        #             for n in ngtrs])
        # okTypes = [ngtrs[i]['name'] for i, r in enumerate(results) if r]
        # print('%s: okTypes: %r; types: %r;' % (p.host, okTypes, p.types))
        # if okTypes:
        #     p.types = okTypes[:]
        #     p.isWorking = True
        # else:
        #     p.types = None
        #     p.isWorking = False
        # print('%s: isWorking: %r;' % (p.host, p.isWorking))
        # p.log('Status: %s' % p.isWorking)


