import struct
from .errors import *


class BaseNegotiator:
    _sem = None
    _attemptsConnect = 0

    async def __call__(self, p):
        result = False
        attempt = 0
        while attempt < self._attemptsConnect:
            with (await self._sem), (await p.sem):
                attempt += 1

                et = p.expectedType
                firstCharNgtr = p._ngtr[0] # 'S' or 'H'
                if et and attempt > 1 and et != firstCharNgtr:
                    result = False
                    p.log('Expected another proxy type')
                    break

                try:
                    await p.connect()
                except ProxyTimeoutError:
                    continue
                except ProxyConnError:
                    break
                else:
                    result = await self.negotiate(p)
                    if result is not None:  # True or False
                        if result:
                            p.expectedType = firstCharNgtr
                            p.log('Set expected proxy type: %s' % firstCharNgtr)
                        break
                finally:
                    p.close()
        return result or False


class Socks5Ngtr(BaseNegotiator):
    name = 'SOCKS5'

    async def negotiate(self, p):
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
                result = await p.check_working()
        return result


class Socks4Ngtr(BaseNegotiator):
    name = 'SOCKS4'

    async def negotiate(self, p):
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
            result = await p.check_working()
        return result


class HttpsNgtr(BaseNegotiator):
    name = 'HTTPS'

    async def negotiate(self, p):
        request = p._CONNECT_request()
        try:
            await p.send(request)
            resp = await p.recv(128)
            httpStatusCode = int(resp[9:12])
        except (ProxyTimeoutError, ProxyRecvError):
            return
        except (ProxyEmptyRecvError, ValueError):
            return False

        if httpStatusCode != 200:
            p.log('Failed (error)')
            return False
        else:
            result = await p.check_working()
        return result


class HttpNgtr(BaseNegotiator):
    name = 'HTTP'

    async def negotiate(self, p):
        result = await p.check_working()
        return result



# class ConnectNgtr(BaseNegotiator):
#     def __init__(self):
#         self.name = 'CONNECT'

#     @connector
#     async def __call__(self, p):
#         try:
#             await p.send((
#                 'CONNECT {host}:443 HTTP/1.1\r\nHost: {host}\r\n'
#                 'User-Agent: {ua}\r\nConnection: keep-alive\r\n\r\n').format(
#                 host=p.judge.host, ua='Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:40.0) '
#                                       'Gecko/20100101 Firefox/40.0').encode())
#             resp = await p.recv(128)
#         except (ProxyTimeoutError, ProxyRecvError):
#             return
#         except ProxyEmptyRecvError:
#             return False

#         httpStatusCode = resp[9:12]
#         if httpStatusCode != b'200':
#             p.log('Failed (error)')
#             return False
#         else:
#             result = await p.check_get_request() # scheme='HTTPS'
#         return result

# def connector(ngtr_fn):
#     async def wrapper(self, p):
#         result = False
#         attempt = 0
#         while attempt < self._attemptsConnect:
#             with (await self.maxConcurrentConnections):
#                 attempt += 1

#                 # et = p.expected_type
#                 # firstCharNgtr = p.ngtr[0]
#                 # if et and attempt > 1 and et != firstCharNgtr:  # 'S' or 'H'
#                 #     result = False
#                 #     p.log('Expected another proxy type')
#                 #     break

#                 try:
#                     await p.connect()
#                 except ProxyTimeoutError:
#                     continue
#                 except ProxyConnError:
#                     break
#                 else:
#                     result = await ngtr_fn(self, p)
#                 finally:
#                     p.close()

#                 # if result is True:
#                 #     p.expected_type = firstCharNgtr
#                 #     p.log('Set expected proxy type: %s' % firstCharNgtr)

#                 if result is not None:  # True or False
#                     break
#         return result or False
#     return wrapper


# def connector(Cls):
#     class Wrapper(Cls):
#         async def __call__(self, p):
#             print('In Wrapper __call__')
#             # if self.__class__ == Wrapper:
#             #     aClass.numInstances += 1
#             result = False
#             attempt = 0
#             while attempt < Cls._attemptsConnect:
#                 with (await Cls.maxConcurrentConnections):
#                     attempt += 1
#                     try:
#                         await p.connect()
#                     except ProxyTimeoutError:
#                         continue
#                     except ProxyConnError:
#                         break
#                     result = await Cls.__call__(self, p) # ngtr_fn(self, p)
#                     p._writer.close()
#                     p.log('Connection: closed')

#                     if result is not None:  # True or False
#                         break
#             return result or False
#     return Wrapper


# class MetaNegotiator(type):
#     def __new__(cls, name, bases, _dict):






