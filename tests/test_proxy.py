import time
from asyncio.streams import StreamReader

import pytest

from proxybroker import Proxy
from proxybroker.errors import ProxyConnError, ProxyTimeoutError, ResolveError
from proxybroker.negotiators import HttpsNgtr
from proxybroker.utils import log as logger

from .utils import ResolveResult, future_iter


@pytest.fixture
def proxy():
    proxy = Proxy('127.0.0.1', '80', timeout=0.1)
    proxy._reader['conn'] = StreamReader()
    return proxy


@pytest.mark.asyncio
async def test_create_by_ip():
    assert isinstance(await Proxy.create('127.0.0.1', '80'), Proxy)
    with pytest.raises(ValueError):
        await Proxy.create('127.0.0.1', '65536')
    with pytest.raises(ResolveError):
        await Proxy.create('256.0.0.1', '80')


@pytest.mark.asyncio
async def test_create_by_domain(mocker):
    f = future_iter([ResolveResult('127.0.0.1', 0)])
    # pytest-mock teardonw is done when existing thr fixture object
    # no need context manager
    # https://github.com/pytest-dev/pytest-mock#note-about-usage-as-context-manager
    mocker.patch('aiodns.DNSResolver.query', side_effect=f)
    proxy = await Proxy.create('testhost.com', '80')
    assert proxy.host == '127.0.0.1'


def test_repr():
    p = Proxy('8.8.8.8', '80')
    p._runtimes = [1, 3, 3]
    p.types.update({'HTTP': 'Anonymous', 'HTTPS': None})
    assert repr(p) == '<Proxy US 2.33s [HTTP: Anonymous, HTTPS] 8.8.8.8:80>'

    p = Proxy('4.4.4.4', '8080')
    p.types.update({'SOCKS4': None, 'SOCKS5': None})
    assert repr(p) == '<Proxy US 0.00s [SOCKS4, SOCKS5] 4.4.4.4:8080>'

    p = Proxy('127.0.0.1', '3128')
    assert repr(p) == '<Proxy -- 0.00s [] 127.0.0.1:3128>'


def test_as_json_w_geo():
    p = Proxy('8.8.8.8', '3128')
    p._runtimes = [1, 3, 3]
    p.types.update({'HTTP': 'Anonymous', 'HTTPS': None})

    json_tpl = {
        'host': '8.8.8.8',
        'port': 3128,
        'geo': {
            'country': {'code': 'US', 'name': 'United States'},
            'region': {'code': 'Unknown', 'name': 'Unknown'},
            'city': 'Unknown',
        },
        'types': [
            {'type': 'HTTP', 'level': 'Anonymous'},
            {'type': 'HTTPS', 'level': ''},
        ],
        'avg_resp_time': 2.33,
        'error_rate': 0,
    }
    assert p.as_json() == json_tpl


def test_as_json_wo_geo():
    p = Proxy('127.0.0.1', '80')
    p.log('MSG', time.time(), ProxyConnError)
    p.stat['requests'] = 4

    json_tpl = {
        'host': '127.0.0.1',
        'port': 80,
        'geo': {
            'country': {'code': '--', 'name': 'Unknown'},
            'region': {'code': 'Unknown', 'name': 'Unknown'},
            'city': 'Unknown',
        },
        'types': [],
        'avg_resp_time': 0,
        'error_rate': 0.25,
    }
    assert p.as_json() == json_tpl


def test_schemes():
    p = Proxy('127.0.0.1', '80')
    p.types.update({'HTTP': 'Anonymous', 'HTTPS': None})
    assert p.schemes == ('HTTP', 'HTTPS')

    p = Proxy('127.0.0.1', '80')
    p.types['HTTPS'] = None
    assert p.schemes == ('HTTPS',)

    p = Proxy('127.0.0.1', '80')
    p.types.update({'SOCKS4': None, 'SOCKS5': None})
    assert p.schemes == ('HTTP', 'HTTPS')


def test_avg_resp_time():
    p = Proxy('127.0.0.1', '80')
    assert p.avg_resp_time == 0.0
    p._runtimes = [1, 3, 4]
    assert p.avg_resp_time == 2.67


def test_error_rate():
    p = Proxy('127.0.0.1', '80')
    p.log('Error', time.time(), ProxyConnError)
    p.log('Error', time.time(), ProxyConnError)
    p.stat['requests'] = 4
    assert p.error_rate == 0.5


def test_geo():
    p = Proxy('127.0.0.1', '80')
    assert p.geo.code == '--'
    assert p.geo.name == 'Unknown'

    p = Proxy('8.8.8.8', '80')
    assert p.geo.code == 'US'
    assert p.geo.name == 'United States'


def test_ngtr():
    p = Proxy('127.0.0.1', '80')
    p.ngtr = 'HTTPS'
    assert isinstance(p.ngtr, HttpsNgtr)
    assert p.ngtr._proxy is p


def test_log(log):
    p = Proxy('127.0.0.1', '80')
    msg = 'MSG'
    stime = time.time()
    err = ProxyConnError

    assert p.get_log() == []
    assert p._runtimes == []

    with log(logger.name, level='DEBUG') as cm:
        p.log(msg)
        p.ngtr = 'HTTP'
        p.log(msg)
        assert ('INFO', msg, 0) in p.get_log()
        assert ('HTTP', msg, 0) in p.get_log()
        assert len(p.stat['errors']) == 0
        assert p._runtimes == []
        assert cm.output == [
            'DEBUG:proxybroker:127.0.0.1:80 [INFO]: MSG; Runtime: 0.00',
            'DEBUG:proxybroker:127.0.0.1:80 [HTTP]: MSG; Runtime: 0.00',
        ]

    p.log(msg, stime, err)
    p.log(msg, stime, err)
    assert len(p.stat['errors']) == 1
    assert sum(p.stat['errors'].values()) == 2
    assert p.stat['errors'][err.errmsg] == 2
    assert round(p._runtimes[-1], 2) == 0.0

    len_runtimes = len(p._runtimes)
    p.log(msg + 'timeout', stime)
    assert len(p._runtimes) == len_runtimes

    msg = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do'
    p.log(msg)
    last_msg = p.get_log()[-1][1]
    cropped = msg[:60] + '...'
    assert last_msg == cropped


@pytest.mark.asyncio
async def test_recv(proxy):
    resp = b'HTTP/1.1 200 OK\r\nContent-Length: 7\r\n\r\nabcdef\n'
    proxy.reader.feed_data(resp)
    assert await proxy.recv() == resp


@pytest.mark.asyncio
async def test_recv_eof(proxy):
    resp = b'HTTP/1.1 200 OK\r\n\r\nabcdef'
    proxy.reader.feed_data(resp)
    proxy.reader.feed_eof()
    assert await proxy.recv() == resp


@pytest.mark.asyncio
async def test_recv_length(event_loop, proxy):
    proxy.reader.feed_data(b'abc')
    assert await proxy.recv(length=3) == b'abc'
    proxy.reader._buffer.clear()

    proxy.reader.feed_data(b'abcdef')
    assert await proxy.recv(length=3) == b'abc'
    assert await proxy.recv(length=3) == b'def'
    proxy.reader._buffer.clear()

    proxy.reader.feed_data(b'ab')
    with pytest.raises(ProxyTimeoutError):
        await proxy.recv(length=3)


@pytest.mark.asyncio
async def test_recv_head_only(event_loop, proxy):
    data = b'HTTP/1.1 200 Connection established\r\n\r\n'
    proxy.reader.feed_data(data)
    assert await proxy.recv(head_only=True) == data
    proxy.reader._buffer.clear()

    data = b'HTTP/1.1 200 OK\r\nServer: 0\r\n\r\n'
    proxy.reader.feed_data(data + b'abcd')
    assert await proxy.recv(head_only=True) == data
    proxy.reader._buffer.clear()

    proxy.reader.feed_data(b'<html>abc</html>')
    with pytest.raises(ProxyTimeoutError):
        await proxy.recv(head_only=True)


@pytest.mark.asyncio
async def test_recv_content_length(proxy):
    resp = b'HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\n{a}\n'
    proxy.reader.feed_data(resp)
    assert await proxy.recv() == resp


@pytest.mark.asyncio
async def test_recv_content_encoding(proxy):
    resp = (
        b'HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\n'
        b'Content-Length: 7\r\n\r\n\x1f\x8b\x08\x00\n\x00\x00'
    )
    proxy.reader.feed_data(resp)
    proxy.reader.feed_eof()
    assert await proxy.recv() == resp


@pytest.mark.asyncio
async def test_recv_content_encoding_without_eof(event_loop, proxy):
    resp = (
        b'HTTP/1.1 200 OK\r\n'
        b'Content-Encoding: gzip\r\n'
        b'Content-Length: 7\r\n\r\n'
        b'\x1f\x8b\x08\x00\n\x00\x00'
    )
    proxy.reader.feed_data(resp)
    with pytest.raises(ProxyTimeoutError):
        await proxy.recv()


@pytest.mark.asyncio
async def test_recv_content_encoding_chunked(proxy):
    resp = (
        b'HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\n'
        b'Transfer-Encoding: chunked\r\n\r\n3\x1f\x8b\x00\r\n0\r\n'
    )
    proxy.reader.feed_data(resp)
    assert await proxy.recv() == resp
    proxy.reader._buffer.clear()

    resp = (
        b'HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\n'
        b'Transfer-Encoding: chunked\r\n\r\n'
        b'5a' + b'\x1f' * 90 + b'\r\n\r\n0\r\n'
    )
    proxy.reader.feed_data(resp)
    assert await proxy.recv() == resp
