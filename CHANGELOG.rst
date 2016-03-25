Change Log
==========


`0.1.4`_ (Unreleased)
---------------------


`0.1.3`_ (2016-03-26)
---------------------

* ``ProxyProvider`` renamed to ``Provider``.
  ``ProxyProvider`` class is deprecated, use ``Provider`` instead
* ``Broker`` now accepts a list of providers and judges not only as strings 
  but also objects of classes ``Provider`` and ``Judge``
* Fixed bug with signal handler on Windows


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

.. _0.1a1: https://github.com/constverum/ProxyBroker/compare/cf465b3
.. _0.1a2: https://github.com/constverum/ProxyBroker/compare/cf465b3...f8e2428
.. _0.1b1: https://github.com/constverum/ProxyBroker/compare/f8e2428...162f261
.. _0.1b2: https://github.com/constverum/ProxyBroker/compare/162f261...1fa10df
.. _0.1b3: https://github.com/constverum/ProxyBroker/compare/1fa10df...8f69ebd
.. _0.1b4: https://github.com/constverum/ProxyBroker/compare/8f69ebd...v0.1b4
.. _0.1: https://github.com/constverum/ProxyBroker/compare/v0.1b4...v0.1
.. _0.1.2: https://github.com/constverum/ProxyBroker/compare/v0.1...v0.1.2
.. _0.1.3: https://github.com/constverum/ProxyBroker/compare/v0.1.2...v0.1.3
.. _0.1.4: https://github.com/constverum/ProxyBroker/compare/v0.1.3...HEAD
