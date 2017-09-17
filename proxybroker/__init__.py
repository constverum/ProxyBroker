"""
Copyright © 2015-2016 Constverum <constverum@gmail.com>. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

__title__ = 'ProxyBroker'
__package__ = 'proxybroker'
__version__ = '0.2.0'
__short_description__ = '[Finder/Checker/Server] Finds public proxies from multiple sources and concurrently checks them. Supports HTTP(S) and SOCKS4/5.'
__author__ = 'Constverum'
__author_email__ = 'constverum@gmail.com'
__url__ = 'https://github.com/constverum/ProxyBroker'
__license__ = 'Apache License, Version 2.0'
__copyright__ = 'Copyright 2015-2016 Constverum'


from .proxy import Proxy
from .judge import Judge
from .providers import Provider
from .checker import Checker
from .server import Server, ProxyPool
from .api import Broker


import logging
import warnings


logger = logging.getLogger('asyncio')
logger.addFilter(logging.Filter('has no effect when using ssl'))

warnings.simplefilter('always', UserWarning)
warnings.simplefilter('once', DeprecationWarning)
