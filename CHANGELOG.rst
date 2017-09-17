
Change Log
==========


`0.2.0`_ (2017-09-17)
---------------------

* Added CLI interface
* Added :meth:`Broker.serve` function.
  Now ProxyBroker can work as a proxy server that distributes incoming requests to a pool of found proxies
* To available types (protocols) added:
    * ``CONNECT:80`` - CONNECT method to port 80
    * ``CONNECT:25`` - CONNECT method to port 25 (SMTP)
* Added new options of checking and filtering proxies.
  :meth:`Broker.find` method has takes new parameters:
  :attr:`post`, :attr:`strict`, :attr:`dnsbl`.
  See documentation for more information
* Added check proxies to support Cookies and Referer
* Added gzip and deflate support
* :class:`Broker` attributes :attr:`max_concurrent_conn` and :attr:`attempts_conn`
  are deprecated, use :attr:`max_conn` and :attr:`max_tries` instead.
* Parameter :attr:`full` in :meth:`Broker.show_stats` is deprecated, use :attr:`verbose` instead
* Parameter :attr:`types` in :meth:`Broker.find` (and :meth:`Broker.serve`) from now is required
* :class:`ProxyChecker` renamed to :class:`Checker`.
  :class:`ProxyChecker` class is deprecated, use :class:`Checker` instead
* :attr:`Proxy.avgRespTime` renamed to :attr:`Proxy.avg_resp_time`.
  :attr:`Proxy.avgRespTime` is deprecated, use :attr:`Proxy.avg_resp_time` instead
* Improved documentation
* Major refactoring


`0.1.4`_ (2016-04-07)
---------------------

* Fixed bug when launched the second time to find proxies `#7`_


`0.1.3`_ (2016-03-26)
---------------------

* ``ProxyProvider`` renamed to ``Provider``.
  ``ProxyProvider`` class is deprecated, use ``Provider`` instead.
* ``Broker`` now accepts a list of providers and judges not only as strings 
  but also objects of classes ``Provider`` and ``Judge``
* Fixed bug with signal handler on Windows `#4`_


`0.1.2`_ (2016-02-27)
---------------------

* Fixed bug with SIGINT on Linux
* Fixed bug with clearing the queue of proxy check.


`0.1`_ (2016-02-23)
-------------------

* Updated and added a few new providers
* Few minor fix


`0.1b4`_ (2016-01-21)
---------------------

* Added a few tests
* Update documentation


`0.1b3`_ (2016-01-16)
---------------------

* Few minor fix


`0.1b2`_ (2016-01-10)
---------------------

* Few minor fix


`0.1b1`_ (2015-12-29)
---------------------

* Changed the name of a PyProxyChecker on ProxyBroker in 
  connection with the expansion of the concept.
* Added support of multiple proxy providers.
* Initial public release on PyPi
* Many improvements and bug fixes


`0.1a2`_ (2015-11-24)
---------------------

* Added support of multiple proxy judges.


`0.1a1`_ (2015-11-11)
---------------------

* Initial commit with function of proxy checking


.. _#4: https://github.com/constverum/ProxyBroker/issues/4
.. _#7: https://github.com/constverum/ProxyBroker/issues/7
.. _0.1a1: https://github.com/constverum/ProxyBroker/compare/cf465b3
.. _0.1a2: https://github.com/constverum/ProxyBroker/compare/cf465b3...f8e2428
.. _0.1b1: https://github.com/constverum/ProxyBroker/compare/f8e2428...162f261
.. _0.1b2: https://github.com/constverum/ProxyBroker/compare/162f261...1fa10df
.. _0.1b3: https://github.com/constverum/ProxyBroker/compare/1fa10df...8f69ebd
.. _0.1b4: https://github.com/constverum/ProxyBroker/compare/8f69ebd...v0.1b4
.. _0.1: https://github.com/constverum/ProxyBroker/compare/v0.1b4...v0.1
.. _0.1.2: https://github.com/constverum/ProxyBroker/compare/v0.1...v0.1.2
.. _0.1.3: https://github.com/constverum/ProxyBroker/compare/v0.1.2...v0.1.3
.. _0.1.4: https://github.com/constverum/ProxyBroker/compare/v0.1.3...v0.1.4
.. _0.2.0: https://github.com/constverum/ProxyBroker/compare/v0.1.4...HEAD
