
import asyncio
import ipaddress
import os.path
import random
import socket
import sys
from collections import namedtuple
from importlib.util import find_spec

import aiodns
import aiohttp
import maxminddb

from .errors import ResolveError
from .utils import DATA_DIR, log

GeoData = namedtuple(
    'GeoData', ['code', 'name', 'region_code', 'region_name', 'city_name']
)

_countrydb = os.path.join(DATA_DIR, 'GeoLite2-Country.mmdb')
_citydb = os.path.join(DATA_DIR, 'GeoLite2-City.mmdb')
_geo_db = _citydb if os.path.exists(_citydb) else _countrydb

_mmdb_reader = maxminddb.open_database(_geo_db)


class Resolver:
    """Async host resolver based on aiodns."""

    _cached_hosts = {}
    _ip_hosts = [
        'https://wtfismyip.com/text',
        'http://api.ipify.org/',
        'http://ipinfo.io/ip',
        'http://ipv4.icanhazip.com/',
        'http://myexternalip.com/raw',
        'http://ipinfo.io/ip',
        'http://ifconfig.io/ip',
    ]
    # the list of resolvers will point a copy of original one
    _temp_host = []

    def __init__(self, timeout=5, loop=None):
        self._timeout = timeout
        self._loop = loop or asyncio.get_event_loop()
        self._resolver = aiodns.DNSResolver(loop=self._loop)

    @staticmethod
    def host_is_ip(host):
        """Check a host is IP address."""
        # TODO: add IPv6 support
        try:
            ipaddress.IPv4Address(host)
        except ipaddress.AddressValueError:
            return False
        else:
            return True

    @staticmethod
    def get_ip_info(ip):
        """Return geo information about IP address.

        `code` - ISO country code
        `name` - Full name of country
        `region_code` - ISO region code
        `region_name` - Full name of region
        `city_name` - Full name of city
        """
        # from pprint import pprint
        try:
            ipInfo = _mmdb_reader.get(ip) or {}
        except (maxminddb.errors.InvalidDatabaseError, ValueError):
            ipInfo = {}

        code, name = '--', 'Unknown'
        city_name, region_code, region_name = ('Unknown',) * 3
        if 'country' in ipInfo:
            code = ipInfo['country']['iso_code']
            name = ipInfo['country']['names']['en']
        elif 'continent' in ipInfo:
            code = ipInfo['continent']['code']
            name = ipInfo['continent']['names']['en']
        if 'city' in ipInfo:
            city_name = ipInfo['city']['names']['en']
        if 'subdivisions' in ipInfo:
            region_code = ipInfo['subdivisions'][0]['iso_code']
            region_name = ipInfo['subdivisions'][0]['names']['en']
        return GeoData(code, name, region_code, region_name, city_name)

    def _pop_random_ip_host(self):
        host = random.choice(self._temp_host)
        self._temp_host.remove(host)
        return host

    async def get_real_ext_ip(self):
        """Return real external IP address."""
        # make a copy of original one to temp one
        # so original one will stay no change
        self._temp_host = self._ip_hosts.copy()
        while self._temp_host:
            try:
                timeout = aiohttp.ClientTimeout(total=self._timeout)
                async with aiohttp.ClientSession(
                    timeout=timeout, loop=self._loop
                ) as session, session.get(self._pop_random_ip_host()) as resp:
                    ip = await resp.text()
            except asyncio.TimeoutError:
                pass
            else:
                ip = ip.strip()
                if self.host_is_ip(ip):
                    log.debug('Real external IP: %s', ip)
                    break
        else:
            raise RuntimeError('Could not get the external IP')
        return ip

    async def resolve(self, host, port=80, family=None, qtype='A', logging=True):
        """Return resolving IP address(es) from host name."""
        if self.host_is_ip(host):
            return host

        _host = self._cached_hosts.get(host)
        if _host:
            return _host

        resp = await self._resolve(host, qtype)

        if resp:
            hosts = [
                {
                    'hostname': host,
                    'host': r.host,
                    'port': port,
                    'family': family,
                    'proto': socket.IPPROTO_IP,
                    'flags': socket.AI_NUMERICHOST,
                }
                for r in resp
            ]
            if family:
                self._cached_hosts[host] = hosts
            else:
                self._cached_hosts[host] = hosts[0]['host']
            if logging:
                log.debug('%s: Host resolved: %s' % (host, self._cached_hosts[host]))
        else:
            if logging:
                log.warning('%s: Could not resolve host' % host)
        return self._cached_hosts.get(host)

    async def _resolve(self, host, qtype):
        try:
            resp = await asyncio.wait_for(
                self._resolver.query(host, qtype), timeout=self._timeout
            )
        except (aiodns.error.DNSError, asyncio.TimeoutError):
            raise ResolveError
        else:
            return resp
