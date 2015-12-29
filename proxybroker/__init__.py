"""
Copyright © 2015 Constverum <constverum@gmail.com>. All rights reserved.

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
__version__ = "0.1b1"
__author__ = 'Constverum'
__license__ = 'Apache 2.0'
__copyright__ = 'Copyright 2015 Constverum'

# import pkg_resources
# pkg_resources.declare_namespace(__name__)
# https://packaging.python.org/en/latest/distributing/
# import logging
# import proxychecker
# print(proxychecker.Proxy)
# from . import devdata
from .proxy import Proxy
from .judge import Judge
from .checker import ProxyChecker
# from .finder import ProxyFinder
from .api import Broker#, find, check, show_stats
# print(Proxy)

