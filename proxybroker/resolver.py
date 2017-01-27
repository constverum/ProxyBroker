import socket
import asyncio
import os.path
import ipaddress
from collections import namedtuple

import aiodns
import aiohttp
import maxminddb

from .errors import *
from .utils import log, BASE_DIR


GeoData = namedtuple('GeoData', ['code', 'name'])
_mmdb_reader = maxminddb.open_database(
    os.path.join(BASE_DIR, 'data', 'GeoLite2-Country.mmdb'))


class Resolver:
    """Async host resolver based on aiodns."""

    _cached_hosts = {}

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

        `code` - ISO code
        `name` - The full name of the country proxy location
        """
        try:
            ipInfo = _mmdb_reader.get(ip) or {}
        except (maxminddb.errors.InvalidDatabaseError, ValueError):
            ipInfo = {}

        code, name = '--', 'Unknown'
        if 'country' in ipInfo:
            code = ipInfo['country']['iso_code']
            name = ipInfo['country']['names']['en']
        elif 'continent' in ipInfo:
            code = ipInfo['continent']['code']
            name = ipInfo['continent']['names']['en']
        return GeoData(code, name)

    async def get_real_ext_ip(self):
        """Return real external IP address."""
        try:
            with aiohttp.Timeout(self._timeout, loop=self._loop):
                async with aiohttp.ClientSession(loop=self._loop) as session,\
                        session.get('http://httpbin.org/ip') as resp:
                    data = await resp.json()
        except asyncio.TimeoutError as e:
            raise RuntimeError('Could not get a external IP. Error: %s' % e)
        else:
            ip = data['origin'].split(', ')[0]
            log.debug('Real external IP: %s' % ip)
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
            hosts = [{'hostname': host, 'host': r.host, 'port': port,
                      'family': family, 'proto': socket.IPPROTO_IP,
                      'flags': socket.AI_NUMERICHOST} for r in resp]
            if family:
                self._cached_hosts[host] = hosts
            else:
                self._cached_hosts[host] = hosts[0]['host']
            if logging:
                log.debug('%s: Host resolved: %s' % (
                    host, self._cached_hosts[host]))
        else:
            if logging:
                log.warning('%s: Could not resolve host' % host)
        return self._cached_hosts.get(host)

    async def _resolve(self, host, qtype):
        try:
            resp = await asyncio.wait_for(self._resolver.query(host, qtype),
                                          timeout=self._timeout)
        except (aiodns.error.DNSError, asyncio.TimeoutError):
            raise ResolveError
        else:
            return resp
