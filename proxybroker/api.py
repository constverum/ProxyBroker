import asyncio

from pprint import pprint
from collections import defaultdict, Counter

from .proxy import Proxy
from .judge import Judge, get_judges
from .checker import ProxyChecker
from .negotiators import BaseNegotiator
from .utils import log, set_my_ip, IPPortPatternLine
from .providers import ProxyProvider, get_providers


class Broker:
    def __init__(self,
                 queue,
                 timeout=8,
                 attempts_conn=3,
                 max_concurrent_conn=200,
                 judges=None,
                 providers=None,
                 verify_ssl=False,
                 loop=None):
        self._qResult = queue
        self._allFoundProxies = []
        self._allFoundProxyPairs = set()
        self._providers = [ProxyProvider(pr) for pr in providers]\
                          if providers else get_providers()
        self._judges = [Judge(u) for u in judges] if judges else get_judges()
        self._loop = loop or asyncio.get_event_loop()
        self._limit = None
        self._countries= None
        self._on_check = []
        self._to_check = []
        self._isDone = False
        self._tasks = None
        self._all_checked = asyncio.Event(loop=self._loop)
        self._all_checked.set()
        self._checker = ProxyChecker(broker=self,
                                     judges=self._judges,
                                     loop=self._loop)
        self._timeout = timeout
        self._cycle_lock = asyncio.Lock()
        self._setup(timeout, attempts_conn, max_concurrent_conn, verify_ssl)

    def _setup(self, timeout, attempts_conn, max_concurrent_conn, verify_ssl):
        if isinstance(max_concurrent_conn, asyncio.Semaphore):
            sem = max_concurrent_conn
        else:
            sem = asyncio.Semaphore(max_concurrent_conn)

        Judge.clear()
        Judge._sem = sem
        Judge._timeout = timeout
        Judge._loop = self._loop
        Judge._verifySSL = verify_ssl
        Proxy._sem = sem
        Proxy._loop = self._loop
        Proxy._timeout = timeout
        Proxy._verifySSL = verify_ssl
        ProxyProvider._sem = sem
        ProxyProvider._loop = self._loop
        BaseNegotiator._sem = sem
        BaseNegotiator._attemptsConnect = attempts_conn

    async def grab(self, *, countries=None, limit=None):
        self._countries = countries
        self._limit = limit
        await self._run(self._grab(types=None, push=self.push_to_result))

    async def find(self, *, data=None, types=None, countries=None, limit=None):
        await set_my_ip(self._timeout, self._loop)
        types = self._update_types(types)
        self._checker.set_conditions(types=types)  # , countries=countries
        self._countries = countries
        self._limit = limit
        if data:
            action = self._load(data, push=self.push_to_check)
        else:
            action = self._grab(types, push=self.push_to_check)

        await self._run(self._checker.check_judges(), action)

    async def _run(self, *args):
        self._tasks = asyncio.gather(*args)
        try:
            await self._tasks
        except asyncio.CancelledError:
            log.info('Cancelled')
        else:
            log.info('Total found proxies: %d' % len(self._allFoundProxies))
            log.info('Found proxy-pairs (%d): %s' % (
                len(self._allFoundProxyPairs), self._allFoundProxyPairs))
            log.info('Wait until all be checked')
            await self._all_checked.wait()
        finally:
            self._done()

    def _update_types(self, types):
        _types = {}
        if not types:
            return _types
        for tp in types:
            lvl = None
            if isinstance(tp, (list, tuple, set)):
                tp, lvl = tp[0], tp[1]
            _types[tp] = lvl
        return _types

    async def _load(self, data, push):
        log.debug('Start load proxies from input data')
        if isinstance(data, str):
            data = IPPortPatternLine.findall(data)
        data = set(data)
        # data: {('192.168.0.1', '80'), ('192.168.0.2', '8080'), ...}
        await self._pipe(data, push=push)

    async def _grab(self, types, push):
        log.debug('Start grabbing proxies')
        providers = [pr for pr in self._providers if not types or\
                     not pr.proto or (pr.proto & types.keys())]
        for pr in providers:
            log.info('Try to get proxies from %s...' % pr.domain)
            proxies = await pr.get_proxies()
            log.info('Provider %s returned %d proxies: %s' % (pr.domain, len(proxies), proxies))
            await self._pipe(proxies, push=push)

    async def _pipe(self, proxies, push):
        with (await self._cycle_lock):
            pushed = 0
            proxies = {(host, port): args for host, port, *args in proxies}
            for host, port in proxies.keys()-self._allFoundProxyPairs:
                self._allFoundProxyPairs.add((host, port))
                args = proxies[(host, port)]
                p = await Proxy.create(host, port, *args)
                if not p:
                    continue
                if host != p.host:
                    self._allFoundProxyPairs.add((p.host, port))
                self._allFoundProxies.append(p)
                if not self._filter(p):
                    continue
                push(p)
                pushed += 1
            log.info('PUSHED: %d of %d' % (pushed, len(proxies)))

    def _filter(self, p):
        # GEO
        if self._countries and (p.geo['code'] not in self._countries):
            p.log('Location of proxy is outside the given countries list')
            return False
        else:
            return True

    def push_to_check(self, p):
        def _put_to_check(p):
            f = asyncio.ensure_future(self._checker.check(p))
            f.add_done_callback(_on_completion)
            self._on_check.append(f)
            self._all_checked.clear()
        def _on_completion(f):
            try:
                self._on_check.remove(f)
            except ValueError:
                return
            if self._to_check:
                _put_to_check(self._to_check.pop())
            elif not self._on_check:
                log.info('All proxies checked')
                self._all_checked.set()

        if len(self._on_check) < 1000:
            _put_to_check(p)
        else:
            self._to_check.append(p)

    def push_to_result(self, p):
        self._qResult.put_nowait(p)
        self._update_limit()

    def _update_limit(self):
        # log.debug('_update_limit:', self._limit)
        if self._limit is not None:
            self._limit -= 1
            if self._limit == 0:
                self._done()

    def _done(self):
        if self._isDone:
            return
        self._isDone = True
        for f in self._on_check:
            if not f.cancelled():
                f.cancel()
        self._tasks.cancel()
        self.push_to_result(None)
        log.debug('Done!')


    def show_stats(self, full=True):
        if not self._allFoundProxies:
            print('Proxy not found')
            return

        errors = Counter()
        [errors.update(p.errors) for p in self._allFoundProxies]

        allWorkingProxies = [p for p in self._allFoundProxies if p.isWorking]

        proxiesByType = {'SOCKS5': [], 'SOCKS4': [],
                         'HTTPS': [], 'HTTP': []}

        stat = {'Wrong country': [],
                'Wrong protocol/anonymity lvl': [],
                'Connection success': [],
                'Connection timeout': [],
                'Connection failed': []}

        for p in sorted(self._allFoundProxies, key=lambda p: p.host):
            msgs = ' '.join([l[0] for l in p.log()])
            pFullLog = [p, ]
            for proto in p.types:
                proxiesByType[proto].append(p)
            if 'Wrong country' in msgs:
                stat['Wrong country'].append(p)
            elif 'Connection: success' in msgs:
                if 'Protocol or the level' in msgs:
                    stat['Wrong protocol/anonymity lvl'].append(p)
                stat['Connection success'].append(p)
                events_by_ngtr = defaultdict(list)
                for event, runtime in p.log():
                    if 'Host resolved' in event:
                        pFullLog.append('\t{:<70} Runtime: {:.4f}'.format(
                                        event.replace('None: ', ''), runtime))
                    else:
                        ngtrChars = event.find(':')
                        ngtr = event[:ngtrChars]
                        # event = 'SOCKS5: Connection: success' =>
                        # ngtr = 'SOCKS5'
                        event = event[ngtrChars+2:]
                        events_by_ngtr[ngtr].append((event, runtime))

                for ngtr, events in sorted(events_by_ngtr.items(),
                                           key=lambda item: item[0]):
                    pFullLog.append('\t%s' % ngtr)
                    for event, runtime in events:
                        if 'Initial connection' in event:
                            continue
                        elif 'Connection:' in event and\
                             'Connection: closed' not in event:
                            pFullLog.append('\t\t{:<66} Runtime: {:.4f}'
                                            .format(event, runtime))
                        else:
                            pFullLog.append('\t\t\t{:<62} Runtime: {:.4f}'
                                            .format(event, runtime))
                if full:
                    for s in pFullLog:
                        print(s)
            elif 'Connection: failed' in msgs:
                stat['Connection failed'].append(p)
            else:
                stat['Connection timeout'].append(p)
        if full:
            print('Stats:')
            pprint(stat)

        lmb = lambda p: (len(p.host[:p.host.find('.')]), p.host[:3])
        s5 = sorted(proxiesByType.get('SOCKS5', []), key=lmb)
        s4 = sorted(proxiesByType.get('SOCKS4', []), key=lmb)
        hs = sorted(proxiesByType.get('HTTPS', []), key=lmb)
        h = sorted(proxiesByType.get('HTTP', []), key=lmb)
        print('The amount of working proxies: {all}\n'
              'SOCKS5 (count: {ls5}): {s5}\nSOCKS4 (count: {ls4}): {s4}\n'
              'HTTPS (count: {lhs}): {hs}\nHTTP (count: {lh}): {h}\n'
              .format(all=len(allWorkingProxies), s5=s5, ls5=len(s5),
                s4=s4, ls4=len(s4), hs=hs, lhs=len(hs), h=h, lh=len(h)))
        print('Errors:', errors)
