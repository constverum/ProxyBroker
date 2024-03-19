import asyncio
import io
import signal
import warnings
from collections import Counter, defaultdict
from functools import partial
from pprint import pprint

from .checker import Checker
from .errors import ResolveError
from .providers import PROVIDERS, Provider
from .proxy import Proxy
from .resolver import Resolver
from .server import Server
from .utils import IPPortPatternLine, log

# Pause between grabbing cycles; in seconds.
GRAB_PAUSE = 180

# The maximum number of providers that are parsed concurrently
MAX_CONCURRENT_PROVIDERS = 3


class Broker:
    """The Broker.

    | One broker to rule them all, one broker to find them,
    | One broker to bring them all and in the darkness bind them.

    :param asyncio.Queue queue: (optional) Queue of found/checked proxies
    :param int timeout: (optional) Timeout of a request in seconds
    :param int max_conn:
        (optional) The maximum number of concurrent checks of proxies
    :param int max_tries:
        (optional) The maximum number of attempts to check a proxy
    :param list judges:
        (optional) Urls of pages that show HTTP headers and IP address.
        Or :class:`~proxybroker.judge.Judge` objects
    :param list providers:
        (optional) Urls of pages where to find proxies.
        Or :class:`~proxybroker.providers.Provider` objects
    :param bool verify_ssl:
        (optional) Flag indicating whether to check the SSL certificates.
        Set to True to check ssl certifications
    :param loop: (optional) asyncio compatible event loop
    :param stop_broker_on_sigint: (optional) whether set SIGINT signal on broker object.
        Useful for a thread other than main thread.

    .. deprecated:: 0.2.0
        Use :attr:`max_conn` and :attr:`max_tries` instead of
        :attr:`max_concurrent_conn` and :attr:`attempts_conn`.
    """

    def __init__(
        self,
        queue=None,
        timeout=8,
        max_conn=200,
        max_tries=3,
        judges=None,
        providers=None,
        verify_ssl=False,
        loop=None,
        stop_broker_on_sigint=True,
        **kwargs,
    ):
        self._loop = loop or asyncio.get_event_loop_policy().get_event_loop()
        self._proxies = queue or asyncio.Queue()
        self._resolver = Resolver(loop=self._loop)
        self._timeout = timeout
        self._verify_ssl = verify_ssl

        self.unique_proxies = {}
        self._all_tasks = []
        self._checker = None
        self._server = None
        self._limit = 0  # not limited
        self._countries = None

        max_concurrent_conn = kwargs.get('max_concurrent_conn')
        if max_concurrent_conn:
            warnings.warn(
                '`max_concurrent_conn` is deprecated, use `max_conn` instead',
                DeprecationWarning,
            )
            if isinstance(max_concurrent_conn, asyncio.Semaphore):
                max_conn = max_concurrent_conn._value
            else:
                max_conn = max_concurrent_conn

        attempts_conn = kwargs.get('attempts_conn')
        if attempts_conn:
            warnings.warn(
                '`attempts_conn` is deprecated, use `max_tries` instead',
                DeprecationWarning,
            )
            max_tries = attempts_conn

        # The maximum number of concurrent checking proxies
        self._on_check = asyncio.Queue(maxsize=max_conn)
        self._max_tries = max_tries
        self._judges = judges
        self._providers = [
            p if isinstance(p, Provider) else Provider(p)
            for p in (providers or PROVIDERS)
        ]
        if stop_broker_on_sigint:
            try:
                self._loop.add_signal_handler(signal.SIGINT, self.stop)
                # add_signal_handler() is not implemented on Win
                # https://docs.python.org/3.5/library/asyncio-eventloops.html#windows
            except NotImplementedError:
                pass

    async def grab(self, *, countries=None, limit=0):
        """Gather proxies from the providers without checking.

        :param list countries: (optional) List of ISO country codes
                               where should be located proxies
        :param int limit: (optional) The maximum number of proxies

        :ref:`Example of usage <proxybroker-examples-grab>`.
        """
        self._countries = countries
        self._limit = limit
        task = asyncio.ensure_future(self._grab(check=False))
        self._all_tasks.append(task)

    async def find(
        self,
        *,
        types=None,
        data=None,
        countries=None,
        post=False,
        strict=False,
        dnsbl=None,
        limit=0,
        **kwargs,
    ):
        """Gather and check proxies from providers or from a passed data.

        :ref:`Example of usage <proxybroker-examples-find>`.

        :param list types:
            Types (protocols) that need to be check on support by proxy.
            Supported: HTTP, HTTPS, SOCKS4, SOCKS5, CONNECT:80, CONNECT:25
            And levels of anonymity (HTTP only): Transparent, Anonymous, High
        :param data:
            (optional) String or list with proxies. Also can be a file-like
            object supports `read()` method. Used instead of providers
        :param list countries:
            (optional) List of ISO country codes where should be located
            proxies
        :param bool post:
            (optional) Flag indicating use POST instead of GET for requests
            when checking proxies
        :param bool strict:
            (optional) Flag indicating that anonymity levels of types
            (protocols) supported by a proxy must be equal to the requested
            types and levels of anonymity. By default, strict mode is off and
            for a successful check is enough to satisfy any one of the
            requested types
        :param list dnsbl:
            (optional) Spam databases for proxy checking.
            `Wiki <https://en.wikipedia.org/wiki/DNSBL>`_
        :param int limit: (optional) The maximum number of proxies

        :raises ValueError:
            If :attr:`types` not given.

        .. versionchanged:: 0.2.0
            Added: :attr:`post`, :attr:`strict`, :attr:`dnsbl`.
            Changed: :attr:`types` is required.
        """
        ip = await self._resolver.get_real_ext_ip()
        types = _update_types(types)

        if not types:
            raise ValueError('`types` is required')

        self._checker = Checker(
            judges=self._judges,
            timeout=self._timeout,
            verify_ssl=self._verify_ssl,
            max_tries=self._max_tries,
            real_ext_ip=ip,
            types=types,
            post=post,
            strict=strict,
            dnsbl=dnsbl,
            loop=self._loop,
        )
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

        The server distributes incoming requests to a pool of found proxies.

        When the server receives an incoming request, it chooses the optimal
        proxy (based on the percentage of errors and average response time)
        and passes to it the incoming request.

        In addition to the parameters listed below are also accept all the
        parameters of the :meth:`.find` method and passed it to gather proxies
        to a pool.

        :ref:`Example of usage <proxybroker-examples-server>`.

        :param str host: (optional) Host of local proxy server
        :param int port: (optional) Port of local proxy server
        :param int limit:
            (optional) When will be found a requested number of working
            proxies, checking of new proxies will be lazily paused.
            Checking will be resumed if all the found proxies will be discarded
            in the process of working with them (see :attr:`max_error_rate`,
            :attr:`max_resp_time`). And will continue until it finds one
            working proxy and paused again. The default value is 100
        :param int max_tries:
            (optional) The maximum number of attempts to handle an incoming
            request. If not specified, it will use the value specified during
            the creation of the :class:`Broker` object. Attempts can be made
            with different proxies. The default value is 3
        :param int strategy:
            (optional) The strategy used for picking proxy from pool.
            The default value is 'best'
        :param int min_queue:
            (optional) The minimum number of proxies to choose from
                before deciding which is the most suitable to use.
                The default value is 5
        :param int min_req_proxy:
            (optional) The minimum number of processed requests to estimate the
            quality of proxy (in accordance with :attr:`max_error_rate` and
            :attr:`max_resp_time`). The default value is 5
        :param int max_error_rate:
            (optional) The maximum percentage of requests that ended with
            an error. For example: 0.5 = 50%. If proxy.error_rate exceeds this
            value, proxy will be removed from the pool.
            The default value is 0.5
        :param int max_resp_time:
            (optional) The maximum response time in seconds.
            If proxy.avg_resp_time exceeds this value, proxy will be removed
            from the pool. The default value is 8
        :param bool prefer_connect:
            (optional) Flag that indicates whether to use the CONNECT method
            if possible. For example: If is set to True and a proxy supports
            HTTP proto (GET or POST requests) and CONNECT method, the server
            will try to use CONNECT method and only after that send the
            original request. The default value is False
        :param list http_allowed_codes:
            (optional) Acceptable HTTP codes returned by proxy on requests.
            If a proxy return code, not included in this list, it will be
            considered as a proxy error, not a wrong/unavailable address.
            For example, if a proxy will return a ``404 Not Found`` response -
            this will be considered as an error of a proxy.
            Checks only for HTTP protocol, HTTPS not supported at the moment.
            By default the list is empty and the response code is not verified
        :param int backlog:
            (optional) The maximum number of queued connections passed to
            listen. The default value is 100

        :raises ValueError:
            If :attr:`limit` is less than or equal to zero.
            Because a parsing of providers will be endless

        .. versionadded:: 0.2.0
        """

        if limit <= 0:
            raise ValueError(
                'In serve mode value of the limit cannot be less than or '
                'equal to zero. Otherwise, a parsing of providers will be '
                'endless'
            )

        self._server = Server(
            host=host,
            port=port,
            proxies=self._proxies,
            timeout=self._timeout,
            max_tries=kwargs.pop('max_tries', self._max_tries),
            loop=self._loop,
            **kwargs,
        )
        self._server.start()

        task = asyncio.ensure_future(self.find(limit=limit, **kwargs))
        self._all_tasks.append(task)

    async def _load(self, data, check=True):
        """Looking for proxies in the passed data.

        Transform the passed data from [raw string | file-like object | list]
        to set {(host, port), ...}: {('192.168.0.1', '80'), }
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
        def _get_tasks(by=MAX_CONCURRENT_PROVIDERS):
            providers = [
                pr
                for pr in self._providers
                if not types or not pr.proto or bool(pr.proto & types.keys())
            ]
            while providers:
                tasks = [
                    asyncio.ensure_future(pr.get_proxies()) for pr in providers[:by]
                ]
                del providers[:by]
                self._all_tasks.extend(tasks)
                yield tasks

        log.debug('Start grabbing proxies')
        while True:
            for tasks in _get_tasks():
                for task in asyncio.as_completed(tasks):
                    proxies = await task
                    for proxy in proxies:
                        await self._handle(proxy, check=check)
            log.debug('Grab cycle is complete')
            if self._server:
                log.debug('fall asleep for %d seconds' % GRAB_PAUSE)
                await asyncio.sleep(GRAB_PAUSE)
                log.debug('awaked')
            else:
                break
        await self._on_check.join()
        self._done()

    async def _handle(self, proxy, check=False):
        try:
            proxy = await Proxy.create(
                *proxy,
                timeout=self._timeout,
                resolver=self._resolver,
                verify_ssl=self._verify_ssl,
                loop=self._loop,
            )
        except (ResolveError, ValueError):
            return

        if not self._is_unique(proxy) or not self._geo_passed(proxy):
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
            log.debug(
                'pause. proxies: %s; limit: %s' % (self._proxies.qsize(), self._limit)
            )
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
        """Stop all tasks, and the local proxy server if it's running."""
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
        """Show statistics on the found proxies.

        Useful for debugging, but you can also use if you're interested.

        :param verbose: Flag indicating whether to print verbose stats

        .. deprecated:: 0.2.0
            Use :attr:`verbose` instead of :attr:`full`.
        """
        if kwargs:
            verbose = True
            warnings.warn(
                '`full` in `show_stats` is deprecated, ' 'use `verbose` instead.',
                DeprecationWarning,
            )

        found_proxies = self.unique_proxies.values()
        num_working_proxies = len([p for p in found_proxies if p.is_working])

        if not found_proxies:
            print('Proxy not found')
            return

        errors = Counter()
        for p in found_proxies:
            errors.update(p.stat['errors'])

        proxies_by_type = {
            'SOCKS5': [],
            'SOCKS4': [],
            'HTTPS': [],
            'HTTP': [],
            'CONNECT:80': [],
            'CONNECT:25': [],
        }

        stat = {
            'Wrong country': [],
            'Wrong protocol/anonymity lvl': [],
            'Connection success': [],
            'Connection timeout': [],
            'Connection failed': [],
        }

        for p in found_proxies:
            msgs = ' '.join([x[1] for x in p.get_log()])
            full_log = [p]
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
                for ngtr, events in sorted(
                    events_by_ngtr.items(), key=lambda item: item[0]
                ):
                    full_log.append('\t%s' % ngtr)
                    for event, runtime in events:
                        if event.startswith('Initial connection'):
                            full_log.append('\t\t-------------------')
                        else:
                            full_log.append(
                                '\t\t{:<66} Runtime: {:.2f}'.format(event, runtime)
                            )
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
