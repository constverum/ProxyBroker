import re
import random
import asyncio
import os.path
import logging
import ipaddress

import aiodns
import aiohttp
import maxminddb

from . import __version__ as version

REAL_IP = None
RESOLVER = None
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log = logging.getLogger(__package__)

IPPattern = re.compile(
    r'(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)')

IPPortPatternLine = re.compile(
    r'^.*?(?P<ip>(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)).*?(?P<port>\d{2,5}).*$',
    flags=re.MULTILINE)

IPPortPatternGlobal = re.compile(
    r'(?P<ip>(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?))'
    r'(?=.*?(?:(?:(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?))|(?P<port>\d{2,5})))',
    flags=re.DOTALL)

# IsIpPattern = re.compile(
#     r'^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$')


mmdbReader = maxminddb.open_database(
                os.path.join(BASE_DIR, 'data', 'GeoLite2-Country.mmdb'))

async def resolve_host(host, timeout, loop):
    global RESOLVER
    if not RESOLVER:
        RESOLVER = aiodns.DNSResolver(loop=loop)
    try:
        ip = await asyncio.wait_for(RESOLVER.query(host, 'A'),
                                    timeout=timeout)
        ip = ip[0].host
    except (aiodns.error.DNSError, asyncio.TimeoutError):
        return False
    else:
        return ip

def get_base_dir():
    return BASE_DIR

def get_path_to_def_judges():
    return os.path.join(BASE_DIR, 'data', 'judges.txt')

def get_path_to_def_providers():
    return os.path.join(BASE_DIR, 'data', 'providers.txt')

def get_headers(rv=False):
    _rv = str(random.randint(1000, 9999))
    headers = {
        # 'User-Agent': 'Mozilla/5.0 (X11; U; Linux i386; ru-RU; rv:2.0) Gecko/20100625 Firefox/3.5.11',
        'User-Agent': 'PrxBroker/%s/%s' % (version, _rv),
        'Accept': '*/*',
        'Accept-Encoding': 'identity;q=0',
        'Pragma': 'no-cache',
        'Cache-control': 'no-cache'
        }
    return headers if not rv else (headers, _rv)


def get_ip_info(ip):
    try:
        ipInfo = mmdbReader.get(ip) or {}
    except (maxminddb.errors.InvalidDatabaseError, ValueError):
        ipInfo = {}

    if 'country' in ipInfo:
        code = ipInfo['country']['iso_code']
        names = ipInfo['country']['names']
    elif 'continent' in ipInfo:
        code = ipInfo['continent']['code']
        names = ipInfo['continent']['names']
    else:
        code = '--'
        names = {'en': 'Unknown'}
    return code, names

def host_is_ip(host):
    # TODO: add IPv6 support
    # return True if IsIpPattern.match(host) else False
    try:
        ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError:
        return False
    else:
        return True

def get_all_ip(page):
    # TODO: add IPv6 support
    return set(IPPattern.findall(page))

async def set_my_ip(timeout=3, loop=None):
    global REAL_IP
    req = aiohttp.get('http://httpbin.org/get?show_env')
    try:
        with aiohttp.Timeout(timeout, loop=loop):
            async with req as resp:
                data = await resp.json()
    except asyncio.TimeoutError as e:
        raise RuntimeError('Could not get a external IP. Error: %s' % e)

    ip = data['origin'].split(', ')[0]
    REAL_IP = ip
    log.debug('Real external IP: %s' % REAL_IP)

def get_my_ip():
    return REAL_IP
