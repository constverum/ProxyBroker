import socket
from unittest.mock import AsyncMock

import pytest

from proxybroker.errors import ResolveError
from proxybroker.resolver import Resolver

from .utils import ResolveResult, future_iter


@pytest.fixture
def resolver():
    return Resolver(timeout=0.1)


def test_host_is_ip(resolver):
    assert resolver.host_is_ip('127.0.0.1') is True
    assert resolver.host_is_ip('256.0.0.1') is False
    assert resolver.host_is_ip('test.com') is False


def test_get_ip_info(resolver):
    ip = resolver.get_ip_info('127.0.0.1')
    assert ip.code == '--'
    assert ip.name == 'Unknown'
    assert ip.region_code == 'Unknown'
    assert ip.region_name == 'Unknown'
    assert ip.city_name == 'Unknown'
    ip = resolver.get_ip_info('8.8.8.8')
    assert ip.code == 'US'
    assert ip.name == 'United States'


@pytest.mark.asyncio
async def test_get_real_ext_ip(event_loop, mocker, resolver):
    async def f(*args, **kwargs):
        return '127.0.0.1\n'

    resp = AsyncMock()
    resp.text = f

    mocker.patch('aiohttp.client.ClientSession._request', return_value=resp)
    assert await resolver.get_real_ext_ip() == '127.0.0.1'


@pytest.mark.asyncio
async def test_resolve(event_loop, mocker, resolver):
    assert await resolver.resolve('127.0.0.1') == '127.0.0.1'

    with pytest.raises(ResolveError):
        await resolver.resolve('256.0.0.1')

    f = future_iter([ResolveResult('127.0.0.1', 0)])
    # https://github.com/pytest-dev/pytest-mock#note-about-usage-as-context-manager
    mocker.patch('aiodns.DNSResolver.query', side_effect=f)
    assert await resolver.resolve('test.com') == '127.0.0.1'


@pytest.mark.asyncio
async def test_resolve_family(mocker, resolver):
    f = future_iter([ResolveResult('127.0.0.2', 0)])
    # https://github.com/pytest-dev/pytest-mock#note-about-usage-as-context-manager
    mocker.patch('aiodns.DNSResolver.query', side_effect=f)
    resp = [
        {
            'hostname': 'test2.com',
            'host': '127.0.0.2',
            'port': 80,
            'family': socket.AF_INET,
            'proto': socket.IPPROTO_IP,
            'flags': socket.AI_NUMERICHOST,
        }
    ]
    resolved = await resolver.resolve('test2.com', family=socket.AF_INET)
    assert resolved == resp


@pytest.mark.asyncio
async def test_resolve_cache(event_loop, mocker, resolver):
    mocker.spy(resolver, '_resolve')
    assert await resolver.resolve('test.com') == '127.0.0.1'
    assert resolver._resolve.call_count == 0

    resolver._cached_hosts.clear()
    f = future_iter(
        [ResolveResult('127.0.0.1', 0)],
        [ResolveResult('127.0.0.2', 0)],
        [Exception],
    )
    with mocker.patch('aiodns.DNSResolver.query', side_effect=f):
        await resolver.resolve('test.com')
        await resolver.resolve('test2.com', port=80, family=socket.AF_INET)
    assert resolver._resolve.call_count == 2

    assert await resolver.resolve('test.com') == '127.0.0.1'
    resp = await resolver.resolve('test2.com')
    assert resp[0]['host'] == '127.0.0.2'
    assert resolver._resolve.call_count == 2

    with mocker.patch('aiodns.DNSResolver.query', side_effect=f), pytest.raises(
        Exception
    ):
        await resolver.resolve('test3.com')
    assert resolver._resolve.call_count == 3
