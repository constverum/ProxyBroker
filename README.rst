ProxyBroker
===========

ProxyBroker is a asynchronous finder working proxies with requested parameters (type, anonymity, country). Supports HTTP(S) and SOCKS proxies!


Features
--------

* Search and collecting proxies from 50 sources (~7k working proxies).
* Identifies proxy in raw input data
* Checks proxies on working with protocols: HTTP, HTTPS, SOCKS4, SOCKS5
* Checks the level of anonymity proxy
* Removes duplicates


Installation
------------

To install ProxyBroker, simply:

.. code-block:: bash

    $ pip install proxybroker


Requirements
------------

* Python 3.5 or higher
* `aiohttp <https://pypi.python.org/pypi/aiohttp>`_
* `aiodns <https://pypi.python.org/pypi/aiodns>`_
* `maxminddb <https://pypi.python.org/pypi/maxminddb>`_


Usage
-----


Broker parameters
"""""""""""""""""

:queue:                 Queue to which will be added proxies
:timeout:               Timeout is set to all the actions carried by the network. In seconds. By default = 8.
:attempts_conn:         Limiting the maximum number of connection attempts. By default = 3.
:max_concurrent_conn:   Limiting the maximum number of concurrent connections. It may be specified as a number,
                        or have used in your program semaphore (*asyncio.Semaphore()*). By default = 200.
:providers:             The list of sites that distribute proxy lists (proxy providers).
:judges:                The list of sites that show http-headers (proxy judges).
                        You can specify a proxy judges or use judges defined by default.
:verify_ssl:            Check ssl certifications? By default = False.
:loop:                  Event loop.


Broker methods
""""""""""""""

:.find(): Searching and checking proxies with requested parameters:

          *data*
              As a source of proxies can be specified raw data. In this case,
              search on the sites with a proxy does not happen. By default is empy.
          *types*
              The list of types (protocols) which must be checked.
              Use a tuple if you want to specify the levels of anonymity: (Type, AnonLvl).
              By default, checks are enabled for all types at all levels of anonymity.
          *countries*
              List of ISO country codes, which must be located proxies.
          *limit*
              Limit the search to a definite number of working proxies.

:.grab(): Only searching the proxies without checking their working. Parameters:

          *countries*
              List of ISO country codes, which must be located proxies.
          *limit*
              Limit the search to a definite number of working proxies.

:.show_stats(): Shows statistics on errors, and proxies log.

          *full*
            If is False (by default) - will show a short version of stats (without proxies log),
            if is True - show full version of stats (with proxies log).


In result you get a proxy objects with the following properties::

    Proxy.host  - The IP address of the proxy
         .port  - The port of the proxy
         .types - The dict of supported protocols and their levels of anonymity


Examples
""""""""


**Basic example**:

.. code-block:: python

    import asyncio
    from proxybroker import Broker

    loop = asyncio.get_event_loop()

    proxies = asyncio.Queue(loop=loop)
    broker = Broker(proxies, loop=loop)

    loop.run_until_complete(broker.find())

    found_proxies = []
    while True:
        proxy = proxies.get_nowait()
        if proxy is None: break
        found_proxies.append(proxy)


**Advanced example**:

.. code-block:: python

    import asyncio
    from proxybroker import Broker

    async def use_example(pQueue):
        while True:
            proxy = await pQueue.get()
            if proxy is None:
                break
            print('Received: %s' % proxy)

    async def find_advanced_example(pQueue, loop):
        broker = Broker(queue=pQueue,
                        timeout=6,
                        attempts_conn=4,
                        max_concurrent_conn=100,
                        judges=['https://httpheader.net/', 'http://httpheader.net/'],
                        providers=['http://www.proxylists.net/', 'http://fineproxy.org/freshproxy/'],
                        verify_ssl=False,
                        loop=loop)

        # only anonymous & high levels of anonymity for http protocol and high for others:
        types = [('HTTP', ('Anonymous', 'High')), 'HTTPS', 'SOCKS4', 'SOCKS5']
        countries = ['US', 'GB', 'DE']
        limit = 10

        await broker.find(types=types, countries=countries, limit=limit)

    if __name__ == '__main__':
        loop = asyncio.get_event_loop()
        pQueue = asyncio.Queue(loop=loop)
        # Start searching and checking.
        # At the same time, using the received proxies to another part of the program
        tasks = asyncio.gather(find_advanced_example(pQueue, loop), use_example(pQueue))
        loop.run_until_complete(tasks)


**Example with your raw data instead of providers**:

.. code-block:: python

    import asyncio
    from proxybroker import Broker

    loop = asyncio.get_event_loop()

    proxies = asyncio.Queue(loop=loop)
    broker = Broker(proxies, loop=loop)

    data = '''10.0.0.1:80
              OK 10.0.0.2:   80 HTTP 200 OK 1.214
              10.0.0.3;80;SOCKS5 check date 21-01-02
              >>>10.0.0.4@80 HTTP HTTPS status OK
              ...'''

    # Note: At the moment, information about the type of proxies in the raw data is ignored
    loop.run_until_complete(broker.find(data=data))

    found_proxies = [proxies.get_nowait() for _ in range(proxies.qsize())]


**Example only collect proxies (without checking)**:

.. code-block:: python
    # ...
    broker = Broker(queue=pQueue, loop=loop)
    await broker.grab(countries=['US'], limit=100)
    # ...


TODO
----

* Check the ping, response time and speed of data transfer
* Check on work with the Cookies/Referrer/POST
* Check site access (Google, Twitter, etc)
* Check proxy on spam. Search proxy ip in spam databases (DNSBL)
* Information about uptime
* Checksum of data returned
* Support for proxy authentication
* Finding outgoing IP for cascading proxy
* The ability to send mail. Check on open 25 port (SMTP)
* The ability to specify the address of the proxy without port (try to connect on defaulted ports)
* The ability to save working proxies to a file (text/json/xml)


License
-------

Licensed under the Apache License, Version 2.0

*This product includes GeoLite2 data created by MaxMind, available from* `http://www.maxmind.com <http://www.maxmind.com>`_.
