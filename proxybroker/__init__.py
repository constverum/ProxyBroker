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
__version__ = '0.1.3'
__short_description__ = '[Finder/Grabber/Checker] Finds public proxies on multiple sources and concurrently checks them (type, anonymity, country). HTTP(S) & SOCKS'
__author__ = 'Constverum'
__author_email__ = 'constverum@gmail.com'
__url__ = 'https://github.com/constverum/ProxyBroker'
__license__ = 'Apache License, Version 2.0'
__copyright__ = 'Copyright 2015-2016 Constverum'


from .proxy import Proxy
from .judge import Judge
from .checker import ProxyChecker
from .api import Broker

