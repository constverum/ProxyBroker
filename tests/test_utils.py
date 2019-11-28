import pytest

from proxybroker.errors import BadStatusLine
from proxybroker.utils import (
    get_all_ip,
    get_status_code,
    parse_headers,
    parse_status_line,
)


def test_get_all_ip():
    page = "abc127.0.0.1:80abc127.0.0.1xx127.0.0.2:8080h"
    assert get_all_ip(page) == {'127.0.0.1', '127.0.0.2'}


def test_get_status_code():
    assert get_status_code('HTTP/1.1 200 OK\r\n') == 200
    assert get_status_code('<html>123</html>\r\n') == 400
    assert get_status_code(b'HTTP/1.1 403 Forbidden\r\n') == 403
    assert get_status_code(b'HTTP/1.1 400 Bad Request\r\n') == 400


def test_parse_status_line():
    assert parse_status_line('HTTP/1.1 200 OK') == {
        'Version': 'HTTP/1.1',
        'Status': 200,
        'Reason': 'OK',
    }
    assert parse_status_line('HTTP/1.1 404 NOT FOUND') == {
        'Version': 'HTTP/1.1',
        'Status': 404,
        'Reason': 'Not Found',
    }
    assert parse_status_line('GET / HTTP/1.1') == {
        'Version': 'HTTP/1.1',
        'Method': 'GET',
        'Path': '/',
    }
    with pytest.raises(BadStatusLine):
        parse_status_line('<!DOCTYPE html ')


def test_parse_headers():
    req = (
        b'GET /go HTTP/1.1\r\nContent-Length: 0\r\nAccept-Encoding: '
        b'gzip, deflate\r\nHost: host.com\r\nConnection: close\r\n\r\n'
    )
    hdrs = {
        'Method': 'GET',
        'Version': 'HTTP/1.1',
        'Path': '/go',
        'Content-Length': '0',
        'Host': 'host.com',
        'Connection': 'close',
        'Accept-Encoding': 'gzip, deflate',
    }
    assert parse_headers(req) == hdrs
    resp = (
        b'HTTP/1.1 200 OK\r\nContent-Length: 1133\r\nConnection: close'
        b'\r\nContent-Type: text/html; charset=UTF-8\r\n\r\n'
    )
    hdrs = {
        'Version': 'HTTP/1.1',
        'Status': 200,
        'Reason': 'OK',
        'Content-Length': '1133',
        'Connection': 'close',
        'Content-Type': 'text/html; charset=UTF-8',
    }
    assert parse_headers(resp) == hdrs
