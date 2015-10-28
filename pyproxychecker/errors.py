from maxminddb.errors import InvalidDatabaseError

class ProxyError(Exception):
    pass


class ProxyConnError(ProxyError):
    pass


class ProxyRecvError(ProxyError):
    pass


class ProxyTimeoutError(ProxyError):
    pass


class ProxyEmptyRecvError(ProxyError):
    pass

class ProxyTypeError(ValueError):
    def __init__(self):
        self.msg = ('Proxy <types> var can be a string '
                    '(ex: "HTTP" or "HTTP,HTTPS") or any '
                    'iterable type (ex: ["HTTP", "HTTPS"])')
        self.args = (self.msg,)

# class ProxyAnonLvlError(ValueError):
#     def __init__(self):
#         self.msg = 'Proxy anonymity levels can be a string '
#                    '(ex: "Transparent" or "Transparent,Anonymous") '
#                    'or any iterable type (ex: ["Anonymous", "High"])'
#         self.args = (self.msg,)

# class ProxyISOCountryError(ValueError):
#     def __init__(self):
#         self.msg = 'ISO country can be a string (ex: "US" or "US,GB,DE") '
#                    'or any iterable type (ex: ["US", "GB", "DE"])'
#         self.args = (self.msg,)
