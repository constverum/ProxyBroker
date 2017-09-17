import re
import random
import os.path
import logging

from . import __version__ as version
from .errors import *

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


def get_headers(rv=False):
    _rv = str(random.randint(1000, 9999)) if rv else ''
    headers = {
        # 'User-Agent': 'Mozilla/5.0 (X11; U; Linux i386; ru-RU; rv:2.0) Gecko/20100625 Firefox/3.5.11',
        'User-Agent': 'PxBroker/%s/%s' % (version, _rv),
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
        'Pragma': 'no-cache',
        'Cache-control': 'no-cache',
        'Cookie': 'cookie=ok',
        'Referer': 'https://www.google.com/'}
    return headers if not rv else (headers, _rv)


def get_all_ip(page):
    # TODO: add IPv6 support
    return set(IPPattern.findall(page))


def get_status_code(resp, start=9, stop=12):
    try:
        code = int(resp[start:stop])
    except ValueError:
        return 400  # Bad Request
    else:
        return code


def parse_status_line(line):
    _headers = {}
    is_response = line.startswith('HTTP/')
    try:
        if is_response:  # HTTP/1.1 200 OK
            version, status, *reason = line.split()
        else:  # GET / HTTP/1.1
            method, path, version = line.split()
    except ValueError:
        raise BadStatusLine(line)

    _headers['Version'] = version.upper()
    if is_response:
        _headers['Status'] = int(status)
        reason = ' '.join(reason)
        reason = reason.upper() if reason.lower() == 'ok' else reason.title()
        _headers['Reason'] = reason
    else:
        _headers['Method'] = method.upper()
        _headers['Path'] = path
        if _headers['Method'] == 'CONNECT':
            host, port = path.split(':')
            _headers['Host'], _headers['Port'] = host, int(port)
    return _headers


def parse_headers(headers):
    headers = headers.decode('utf-8', 'ignore').split('\r\n')
    _headers = {}
    _headers.update(parse_status_line(headers.pop(0)))

    for h in headers:
        if not h:
            break
        name, val = h.split(':', 1)
        _headers[name.strip().title()] = val.strip()

    if ':' in _headers.get('Host', ''):
        host, port = _headers['Host'].split(':')
        _headers['Host'], _headers['Port'] = host, int(port)
    return _headers
