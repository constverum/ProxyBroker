from unittest.mock import call

import pytest

from proxybroker import Proxy
from proxybroker.errors import BadResponseError, BadStatusError
from proxybroker.negotiators import _CONNECT_request

from .utils import future_iter


@pytest.fixture
def proxy(mocker):
    proxy = Proxy('127.0.0.1', '80', timeout=0.1)
    mocker.patch.multiple(
        proxy, send=mocker.DEFAULT, recv=mocker.DEFAULT, connect=mocker.DEFAULT
    )
    yield proxy
    mocker.stopall()


@pytest.mark.parametrize(
    'ngtr,check_anon_lvl,use_full_path',
    [
        ('SOCKS5', False, False),
        ('SOCKS4', False, False),
        ('CONNECT:80', False, False),
        ('CONNECT:25', False, False),
        ('HTTPS', False, False),
        ('HTTP', True, True),
    ],
)
def test_base_attrs(proxy, ngtr, check_anon_lvl, use_full_path):
    proxy.ngtr = ngtr
    assert proxy.ngtr.name == ngtr
    assert proxy.ngtr.check_anon_lvl is check_anon_lvl
    assert proxy.ngtr.use_full_path is use_full_path


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'ngtr,port,recv,expected',
    [
        (
            'SOCKS5',
            80,
            [b'\x05\x00', b'\x05\x00\x00\x01\xc0\xa8\x00\x18\xce\xdf'],
            [call(b'\x05\x01\x00'), call(b'\x05\x01\x00\x01\x7f\x00\x00\x01\x00P')],
        ),
        (
            'SOCKS5',
            443,
            [b'\x05\x00', b'\x05\x00'],
            [call(b'\x05\x01\x00'), call(b'\x05\x01\x00\x01\x7f\x00\x00\x01\x01\xbb')],
        ),  # noqa
        (
            'SOCKS4',
            80,
            future_iter(b'\x00Z\x00\x00\x00\x00\x00\x00'),
            [call(b'\x04\x01\x00P\x7f\x00\x00\x01\x00')],
        ),
        (
            'SOCKS4',
            443,
            future_iter(b'\x00Z\x00\x00\x00\x00\x00\x00'),
            [call(b'\x04\x01\x01\xbb\x7f\x00\x00\x01\x00')],
        ),
    ],
)
async def test_socks_negotiate(proxy, ngtr, port, recv, expected):
    proxy.ngtr = ngtr
    proxy.send.side_effect = future_iter(None, None)
    proxy.recv.side_effect = recv

    await proxy.ngtr.negotiate(ip='127.0.0.1', port=port)

    last_msg = proxy.get_log()[-1][1]
    assert last_msg == 'Request is granted'

    assert proxy.send.call_args_list == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'ngtr,recv,expected',
    [
        # wrong response:
        ('SOCKS5', [b'\x05\xff'], [call(b'\x05\x01\x00')]),
        (
            'SOCKS4',
            future_iter(b'HTTP/1.1 400 Bad Request'),
            [call(b'\x04\x01\x00P\x7f\x00\x00\x01\x00')],
        ),  # noqa
        # failed to connect:
        (
            'SOCKS5',
            (b'\x05\x00', b'\x05\x05'),
            [call(b'\x05\x01\x00'), call(b'\x05\x01\x00\x01\x7f\x00\x00\x01\x00P')],
        ),  # noqa
        (
            'SOCKS4',
            future_iter(b'\x00['),
            [call(b'\x04\x01\x00P\x7f\x00\x00\x01\x00')],
        ),  # noqa
    ],
)
async def test_socks_negotiate_error(proxy, ngtr, recv, expected):
    proxy.ngtr = ngtr
    proxy.send.side_effect = future_iter(None, None)
    proxy.recv.side_effect = recv

    with pytest.raises(BadResponseError):
        await proxy.ngtr.negotiate(ip='127.0.0.1')

    assert proxy.send.call_args_list == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'ngtr,port,recv',
    [
        (
            'CONNECT:80',
            80,
            [b'HTTP/1.1 200 Connection established\r\n\r\n'],
        ),  # noqa
        (
            'CONNECT:25',
            25,
            [
                b'HTTP/1.1 200 Connection established\r\n\r\n',
                b'220 smtp2.test.com',
            ],
        ),  # noqa
        (
            'HTTPS',
            443,
            [b'HTTP/1.1 200 Connection established\r\n\r\n'],
        ),  # noqa
    ],
)
async def test_connect_negotiate(proxy, ngtr, port, recv):
    host = 'test.com'
    proxy.ngtr = ngtr
    proxy.send.side_effect = future_iter(None)
    proxy.recv.side_effect = recv
    proxy.connect.side_effect = future_iter(None)

    await proxy.ngtr.negotiate(host=host)

    req = _CONNECT_request(host=host, port=port)
    assert proxy.send.call_args_list == [call(req)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'ngtr,recv',
    [
        ('CONNECT:80', [b'HTTP/1.1 400 Bad Request\r\n\r\n']),
        (
            'CONNECT:80',
            [b'<html>\r\n<head><title>400 Bad Request</title></head>\r\n'],
        ),  # noqa
        ('CONNECT:25', [b'HTTP/1.1 400 Bad Request\r\n\r\n']),
        (
            'CONNECT:25',
            [b'<html>\r\n<head><title>400 Bad Request</title></head>\r\n'],
        ),  # noqa
        ('CONNECT:25', [b'HTTP/1.1 200 OK\r\n\r\n', b'']),
        ('HTTPS', [b'HTTP/1.1 400 Bad Request\r\n\r\n']),
        (
            'HTTPS',
            [b'<html>\r\n<head><title>400 Bad Request</title></head>\r\n'],
        ),  # noqa
    ],
)
async def test_connect_negotiate_error(proxy, ngtr, recv):
    host = 'test.com'
    proxy.ngtr = ngtr
    proxy.send.side_effect = future_iter(None)
    proxy.recv.side_effect = recv
    proxy.connect.side_effect = future_iter(None)

    with pytest.raises(BadStatusError):
        await proxy.ngtr.negotiate(host=host)
