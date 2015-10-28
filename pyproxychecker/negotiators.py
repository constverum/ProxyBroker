import ssl
import time
import struct
import asyncio

from .errors import *
from .utils import connector


class BaseNegotiator:
    timeout = 0
    attemptsConnect = 0
    sslContext = None
    # def __init__(self):
    #     pass
    # def get_request(self, p, name):  # ngtr, host=None, bip=None
    #     if name == 'SOCKS5-Init':
    #         req = struct.pack('3B', 5, 1, 0)
    #     elif name == 'SOCKS5-Conn':
    #         req = struct.pack('>8BH', 5, 1, 0, 1, *p.judge.bip, 80)
    #     elif name == 'SOCKS4':
    #         req = struct.pack('>2BH5B', 4, 1, 80, *p.judge.bip, 0)
    #     elif name == 'CONNECT':
    #         req = ('CONNECT {host}:80 HTTP/1.1\r\nHost: {host}\r\n'
    #                'Connection: keep-alive\r\n\r\n').format(
    #                 host=p.judge.host).encode()
    #     elif name == 'GET':
    #         req = ('GET {page} HTTP/1.1\r\nHost: {host}\r\n'
    #                'Accept: *.*, */*\r\nConnection: close\r\n\r\n')
    #     return request


class Socks5Ngtr(BaseNegotiator):
    def __init__(self):
        self.name = 'SOCKS5'

    @connector
    async def __call__(self, p):
        try:
            await p.send(struct.pack('3B', 5, 1, 0))
            resp = await p.recv(2)
        except (ProxyTimeoutError, ProxyRecvError):
            return
        except ProxyEmptyRecvError:
            return False

        if resp[0] == 0x05 and resp[1] == 0xff:
            p.log('Failed (auth is required)')
            return False
        elif resp[0] != 0x05 or resp[1] != 0x00:
            p.log('Failed (invalid data)')
            return False
        else:
            try:
                await p.send(struct.pack('>8BH', 5, 1, 0, 1, *p.judge.bip, 80))
                resp = await p.recv(10)
            except (ProxyTimeoutError, ProxyRecvError, ProxyEmptyRecvError):
                return

            if resp[0] != 0x05 or resp[1] != 0x00:
                p.log('Failed (invalid data)')
                return
            else:
                p.log('Request granted')
                result = await p.check_get_request() # scheme='HTTP'
        return result


class Socks4Ngtr(BaseNegotiator):
    def __init__(self):
        self.name = 'SOCKS4'

    @connector
    async def __call__(self, p):
        try:
            await p.send(struct.pack('>2BH5B', 4, 1, 80, *p.judge.bip, 0))
            resp = await p.recv(8)
        except (ProxyTimeoutError, ProxyRecvError):
            return
        except ProxyEmptyRecvError:
            return False

        if resp[0] != 0x00 or resp[1] != 0x5A:
            p.log('Failed (invalid data)')
            return False
        # resp = b'\x00Z\x00\x00\x00\x00\x00\x00' // ord('Z') == 90 == 0x5A
        else:
            p.log('Request granted')
            result = await p.check_get_request() # scheme='HTTP'
        return result


class ConnectNgtr(BaseNegotiator):
    def __init__(self):
        self.name = 'CONNECT'

    @connector
    async def __call__(self, p):
        try:
            await p.send(('CONNECT {host}:80 HTTP/1.1\r\nHost: {host}\r\n'
                         'Connection: keep-alive\r\n\r\n').format(
                          host=p.judge.host).encode())
            resp = await p.recv(128)
        except (ProxyTimeoutError, ProxyRecvError):
            return
        except ProxyEmptyRecvError:
            return False

        httpStatusCode = resp[9:12]
        if httpStatusCode != b'200':
            p.log('Failed (error)')
            return False
        else:
            result = await p.check_get_request() # scheme='HTTPS'
        return result


class HttpsNgtr(BaseNegotiator):
    def __init__(self):
        self.name = 'HTTPS'

    @connector
    async def __call__(self, p):
        try:
            await p.send(('CONNECT {host}:443 HTTP/1.1\r\nHost: {host}\r\n'
                         'Connection: keep-alive\r\n\r\n').format(
                          host=p.judge.host).encode())
            resp = await p.recv(128)
        except (ProxyTimeoutError, ProxyRecvError):
            return
        except ProxyEmptyRecvError:
            return False

        httpStatusCode = resp[9:12]
        if httpStatusCode != b'200':
            p.log('Failed (error)')
            return False
        else:
            sock = p.writer.get_extra_info('socket')
            stime = time.time()
            try:
                # like aiohttp/connector.py ProxyConnector._create_connection()
                p.reader, p.writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        ssl=self.sslContext, sock=sock,
                        server_hostname=p.host),
                    timeout=self.timeout)
                msg = 'SSL: enabled'
            except (ConnectionResetError, OSError):
                # OSError: [Errno 9] Bad file descriptor
                msg = 'SSL: failed'
                return
            except asyncio.TimeoutError:
                msg = 'SSL: timeout'
                return
            except ssl.SSLError as e:
                msg = 'SSL: %s' % e
                return False
            finally:
                p.log(msg, stime)
            result = await p.check_get_request() # scheme='HTTPS'
        return result


class HttpNgtr(BaseNegotiator):
    def __init__(self):
        self.name = 'HTTP'

    @connector
    async def __call__(self, p):
        result = await p.check_get_request() # scheme='HTTP'
        return result
