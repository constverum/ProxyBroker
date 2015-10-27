class ProxyError(Exception):
    pass
    # def __init__(self, msg):
    #     self.args = (msg,)
    #     self.msg = msg


class ProxyConnError(ProxyError):
    pass


class ProxyRecvError(ProxyError):
    pass


class ProxyTimeoutError(ProxyError):
    pass


class ProxyEmptyRecvError(ProxyError):
    pass
