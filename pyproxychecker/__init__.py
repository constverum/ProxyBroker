# import pkg_resources
# pkg_resources.declare_namespace(__name__)
# https://packaging.python.org/en/latest/distributing/
import logging
# import proxychecker
# print(proxychecker.Proxy)
from . import devdata
from .checker import Proxy, Judge, ProxyChecker
# print(Proxy)

__version__ = "0.1dev1"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(message)s',
    datefmt='[%H:%M:%S]',
    level=logging.DEBUG)
