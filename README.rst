==============
PyProxyChecker
==============

PyProxyChecker is a asynchronous proxy checker.

* Asynchronous check
* Check proxy lists for working with protocols: HTTP, CONNECT(HTTPS), SOCKS4, SOCKS5
* Check the level of anonymity proxy
* Recognize different formats of proxy list (specifying the type of proxy and without);
* Remove duplicate
* Returns living proxy requested type (or all types)

.. Can check HTTP proxies for HTTPS (HTTP + SSL) support;
.. Can check HTTP proxies for FTP support;

Requirements:
-------------
* Python 3.5 or higher

Usage:
------
PyProxyChecker accepts proxies in format::

    ip:port
    domain:port

You can also specify the type of proxy::

    ip:port:SOCKS4
    ip:port:HTTP,CONNECT

**Note**:
    * If the type of proxy is specified, it will be tested only the specified protocols.
    * If the type of proxy is **not** specified, it will be tested for all possible protocols.

To check the level of anonymity, the script sends requests to external sites (proxy judge), which provide information on the received http-headers.
You can set a list of such sites judges manually or let the script to find them for you automatically.

Example
~~~~~~~~~

Basic example:

.. Mixed proxy list at input and automatic search for the proxy judges.

::

    from pyproxychecker import ProxyChecker

    proxies = ['192.168.1.1:8000',
               '192.168.1.2:3128:HTTP',
               '192.168.1.3:1080:SOCKS4,SOCKS5']

    worker = ProxyChecker(proxies)
    worker.start()
    liveProxies = worker.get_good_proxies()

    print(liveProxies)
    # Output:
    # <Proxy [HTTP: Anonymous] 192.168.1.2:3128>,
    # <Proxy [SOCKS5: High] 192.168.1.3:1080>,

You got a proxy objects with the following properties::

    Proxy.ptype      - The list of supported protocols
         .anonymity  - The dict of supported protocols and their level of anonymity
         .host       - The IP address of the proxy
         .port       - The port of the proxy

You can override the default values of checking. Timeout and attempts a connection::

    ...
    worker = ProxyChecker(proxies, timeout=6, connects=3)
    ...

Example of a manual specifying the proxy judges::

    ...
    judges = ['http://proxyjudge.info/',
              'http://proxyjudge.us/']

    worker = ProxyChecker(proxies, judges=judges)
    ...

Instead of getting a list of all the living proxy you can get a list of only the specific type of proxy::

    liveProxies = worker.get_good_proxies('SOCKS5')

TODO
----

* Support for authentication (ip:port:login:pass)
* Check the ping
* The ability to specify the address of the proxy without port (try to connect on defaulted ports)
* The ability to save live proxies to a file (in formats: text / json / xml)

License
-------

Licensed under the Apache License, Version 2.0

