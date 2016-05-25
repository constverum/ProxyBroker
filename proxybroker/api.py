import io
import signal
import asyncio
import warnings
from pprint import pprint
from functools import partial
from collections import defaultdict, Counter

from .proxy import Proxy
from .server import Server
from .checker import Checker
from .utils import log, IPPortPatternLine
from .resolver import Resolver
from .providers import Provider, get_providers


warnings.simplefilter('always', DeprecationWarning)
GRAB_PAUSE = 180  # Pause between the cycles grabbing; in seconds


class Broker:
    """Broker."""

    def __init__(self, queue=None, timeout=8, max_conn=200, max_tries=3,
                 judges=None, providers=None, verify_ssl=False, loop=None,
                 **kwargs):
        self._loop = loop or asyncio.get_event_loop()
        self._proxies = queue or asyncio.Queue(loop=self._loop)
        self._resolver = Resolver(loop=self._loop)
        self._timeout = timeout
        self._verify_ssl = verify_ssl

        self.unique_proxies = {}
        self._all_tasks = []
        self._checker = None
        self._server = None
        self._limit = 0
        self._countries = None

        max_concurrent_conn = kwargs.get('max_concurrent_conn')
        if max_concurrent_conn:
            warnings.warn('`max_concurrent_conn` is deprecated, use `max_conn` instead.',
                          DeprecationWarning)
            if isinstance(max_concurrent_conn, asyncio.Semaphore):
                max_conn = max_concurrent_conn._value
            else:
                max_conn = max_concurrent_conn

        attempts_conn = kwargs.get('attempts_conn')
        if attempts_conn:
            warnings.warn('`attempts_conn` is deprecated, use `max_tries` instead.',
                          DeprecationWarning)
            max_tries = attempts_conn

        # Limit the maximum number of concurrent checking proxies
        self._on_check = asyncio.Queue(maxsize=max_conn, loop=self._loop)
        self._max_tries = max_tries
        self._judges = judges
        self._providers = providers

        try:
            self._loop.add_signal_handler(signal.SIGINT, self.stop)
            # add_signal_handler() is not implemented on Win
            # https://docs.python.org/3.5/library/asyncio-eventloops.html#windows
        except NotImplementedError:
            pass

    async def grab(self, *, countries=None, limit=0):
        """Grab proxies from the providers."""
        self._countries = countries
        self._limit = limit
        task = asyncio.ensure_future(self._grab(check=False))
        self._all_tasks.append(task)

    async def find(self, *, types=None, data=None, countries=None,
                   post=False, strict=False, dnsbl=None, limit=0, **kwargs):
        """Find and check proxies.

        Grab proxies from the providers or a raw data and then check them on
        geo location and working with specified types (protocols).
        """
        ip = await self._resolver.get_real_ext_ip()
        types = _update_types(types)

        if not types:
            raise ValueError('Types (protocols) are required.')

        self._checker = Checker(
            judges=self._judges, timeout=self._timeout, verify_ssl=self._verify_ssl,
            max_tries=self._max_tries, real_ext_ip=ip, types=types, post=post,
            strict=strict, dnsbl=dnsbl, loop=self._loop)
        self._countries = countries
        self._limit = limit

        tasks = [asyncio.ensure_future(self._checker.check_judges())]
        if data:
            task = asyncio.ensure_future(self._load(data, check=True))
        else:
            task = asyncio.ensure_future(self._grab(types, check=True))
        tasks.append(task)
        self._all_tasks.extend(tasks)

    def serve(self, host='127.0.0.1', port=8888, limit=100, **kwargs):
        """Start a local proxy server.

        Server distributes incoming requests to a pool of found proxies.

        Controls the rate of error on proxy servers (``min_req_proxy`` &
        ``max_error_rate``), when the rate is greater than the specified -
        removes proxy from the pool of servers used.
        """
        self._server = Server(
            host=host, port=port, proxies=self._proxies, timeout=self._timeout,
            max_tries=self._max_tries, loop=self._loop, **kwargs)
        self._server.start()

        task = asyncio.ensure_future(self.find(limit=limit, **kwargs))
        self._all_tasks.append(task)

    async def _load(self, data, check=True):
        """Transform data from raw string or list to set {(host, port), ...}.

        {('192.168.0.1', '80'), ('192.168.0.2', '8080'), ...}
        """
        log.debug('Load proxies from the raw data')
        if isinstance(data, io.TextIOWrapper):
            data = data.read()
        if isinstance(data, str):
            data = IPPortPatternLine.findall(data)
        proxies = set(data)
        for proxy in proxies:
            await self._handle(proxy, check=check)
        await self._on_check.join()
        self._done()

    async def _grab(self, types=None, check=False):
        # TODO: need refactoring
        log.debug('Start grabbing proxies')
        providers = get_providers(self._providers)
        providers = [pr for pr in providers
                     if not types or not pr.proto or bool(pr.proto & types.keys())]

        if not check:
            tasks = [asyncio.ensure_future(pr.get_proxies()) for pr in providers]
            self._all_tasks.extend(tasks)
            for task in asyncio.as_completed(tasks):
                proxies = await task
                for proxy in proxies:
                    await self._handle(proxy, check=check)
        else:
            while True:
                for pr in providers:
                    proxies = await pr.get_proxies()
                    for proxy in proxies:
                        await self._handle(proxy, check=check)
                log.debug('Grab cycle is complete')
                if self._server:
                    log.debug('sleeped')
                    await asyncio.sleep(GRAB_PAUSE)
                    log.debug('unsleeped')
                else:
                    break
            await self._on_check.join()
        self._done()

    async def _handle(self, proxy, check=False):
        proxy = await Proxy.create(
            *proxy, timeout=self._timeout, resolver=self._resolver,
            verify_ssl=self._verify_ssl, loop=self._loop)

        if not proxy or (proxy and
           not self._is_unique(proxy) or not self._geo_passed(proxy)):
            return

        if check:
            await self._push_to_check(proxy)
        else:
            self._push_to_result(proxy)

    def _is_unique(self, proxy):
        if (proxy.host, proxy.port) not in self.unique_proxies:
            self.unique_proxies[(proxy.host, proxy.port)] = proxy
            return True
        else:
            return False

    def _geo_passed(self, proxy):
        if self._countries and (proxy.geo.code not in self._countries):
            proxy.log('Location of proxy is outside the given countries list')
            return False
        else:
            return True

    async def _push_to_check(self, proxy):
        def _task_done(proxy, f):
            self._on_check.task_done()
            if not self._on_check.empty():
                self._on_check.get_nowait()
            try:
                if f.result():
                    # proxy is working and its types is equal to the requested
                    self._push_to_result(proxy)
            except asyncio.CancelledError:
                pass

        if self._server and not self._proxies.empty() and self._limit <= 0:
            log.debug('pause. proxies: %s; limit: %s' % (
                self._proxies.qsize(), self._limit))
            await self._proxies.join()
            log.debug('unpause. proxies: %s' % self._proxies.qsize())

        await self._on_check.put(None)
        task = asyncio.ensure_future(self._checker.check(proxy))
        task.add_done_callback(partial(_task_done, proxy))
        self._all_tasks.append(task)

    def _push_to_result(self, proxy):
        log.debug('push to result: %r' % proxy)
        self._proxies.put_nowait(proxy)
        self._update_limit()

    def _update_limit(self):
        self._limit -= 1
        if self._limit == 0 and not self._server:
            self._done()

    def stop(self):
        self._done()
        if self._server:
            self._server.stop()
            self._server = None
        log.info('Stop!')

    def _done(self):
        log.debug('called done')
        while self._all_tasks:
            task = self._all_tasks.pop()
            if not task.done():
                task.cancel()
        self._push_to_result(None)
        log.info('Done! Total found proxies: %d' % len(self.unique_proxies))

    def show_stats(self, verbose=False, **kwargs):
        if kwargs:
            verbose = True
            warnings.warn('argument `full` in `show_stats` is deprecated, '
                          'use `verbose` instead.', DeprecationWarning)

        found_proxies = self.unique_proxies.values()
        num_working_proxies = len([p for p in found_proxies if p.is_working])

        if not found_proxies:
            print('Proxy not found')
            return

        errors = Counter()
        for p in found_proxies:
            errors.update(p.stat['errors'])

        proxies_by_type = {'SOCKS5': [], 'SOCKS4': [], 'HTTPS': [], 'HTTP': [],
                           'CONNECT:80': [], 'CONNECT:25': []}

        stat = {'Wrong country': [],
                'Wrong protocol/anonymity lvl': [],
                'Connection success': [],
                'Connection timeout': [],
                'Connection failed': []}

        for p in found_proxies:
            msgs = ' '.join([l[1] for l in p.get_log()])
            full_log = [p, ]
            for proto in p.types:
                proxies_by_type[proto].append(p)
            if 'Location of proxy' in msgs:
                stat['Wrong country'].append(p)
            elif 'Connection: success' in msgs:
                if 'Protocol or the level' in msgs:
                    stat['Wrong protocol/anonymity lvl'].append(p)
                stat['Connection success'].append(p)
                if not verbose:
                    continue
                events_by_ngtr = defaultdict(list)
                for ngtr, event, runtime in p.get_log():
                    events_by_ngtr[ngtr].append((event, runtime))
                for ngtr, events in sorted(events_by_ngtr.items(),
                                           key=lambda item: item[0]):
                    full_log.append('\t%s' % ngtr)
                    for event, runtime in events:
                        if event.startswith('Initial connection'):
                            full_log.append('\t\t-------------------')
                        else:
                            full_log.append('\t\t{:<66} Runtime: {:.2f}'
                                            .format(event, runtime))
                for row in full_log:
                    print(row)
            elif 'Connection: failed' in msgs:
                stat['Connection failed'].append(p)
            else:
                stat['Connection timeout'].append(p)
        if verbose:
            print('Stats:')
            pprint(stat)

        print('The number of working proxies: %d' % num_working_proxies)
        for proto, proxies in proxies_by_type.items():
            print('%s (%s): %s' % (proto, len(proxies), proxies))
        print('Errors:', errors)


def _update_types(types):
    _types = {}
    if not types:
        return _types
    elif isinstance(types, dict):
        return types
    for tp in types:
        lvl = None
        if isinstance(tp, (list, tuple, set)):
            tp, lvl = tp[0], tp[1]
            if isinstance(lvl, str):
                lvl = lvl.split()
        _types[tp] = lvl
    return _types
