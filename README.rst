ProxyBroker
===========
.. image:: https://img.shields.io/pypi/v/proxybroker.svg
    :target: https://pypi.python.org/pypi/proxybroker/
.. image:: https://img.shields.io/pypi/pyversions/proxybroker.svg
    :target: https://pypi.python.org/pypi/proxybroker/
.. image:: https://img.shields.io/travis/constverum/ProxyBroker.svg
    :target: https://travis-ci.org/constverum/ProxyBroker
.. image:: https://img.shields.io/pypi/wheel/proxybroker.svg
    :target: https://pypi.python.org/pypi/proxybroker/
.. image:: https://img.shields.io/pypi/dm/proxybroker.svg
    :target: https://pypi.python.org/pypi/proxybroker/
.. image:: https://img.shields.io/pypi/l/proxybroker.svg
    :target: https://pypi.python.org/pypi/proxybroker/


ProxyBroker is an open source tool that asynchronously finds public proxies on multiple sources and concurrently checks them (type, anonymity level, country). Supports HTTP(S) and SOCKS.

.. image:: https://raw.githubusercontent.com/constverum/ProxyBroker/master/proxybroker/data/example.gif

.. contents::
   :depth: 3

Features
--------

* Finds proxies on 50+ sources (~7k working proxies)
* Identifies proxy in raw input data
* Checks proxies on working with protocols: HTTP, HTTPS, SOCKS4, SOCKS5
* Checks the level of anonymity proxy
* Removes duplicates


Requirements
------------

* Python **3.5** or higher
* `aiohttp <https://pypi.python.org/pypi/aiohttp>`_
* `aiodns <https://pypi.python.org/pypi/aiodns>`_
* `maxminddb <https://pypi.python.org/pypi/maxminddb>`_


Installation
------------

To install last stable release from pypi:

.. code-block:: bash

    $ pip install proxybroker

Or install development version:

.. code-block:: bash

    $ git clone https://github.com/constverum/ProxyBroker.git
    $ cd ProxyBroker
    $ python setup.py install


Examples
--------

Basic example
"""""""""""""

.. code-block:: python

    import asyncio
    from proxybroker import Broker

    loop = asyncio.get_event_loop()

    proxies = asyncio.Queue(loop=loop)
    broker = Broker(proxies, loop=loop)

    loop.run_until_complete(broker.find(limit=4))

    while True:
        proxy = proxies.get_nowait()
        if proxy is None: break
        print('Found proxy: %s' % proxy)

As the final result we get the ``Proxy`` objects. And we can get all the information we need through `Proxy properties`_.

.. code-block:: bash

    Found proxy: <Proxy AU 0.72s [HTTP: Transparent] 1.1.1.1:80>
    Found proxy: <Proxy FR 0.33s [HTTP: High, HTTPS] 2.2.2.2:3128>
    Found proxy: <Proxy US 1.11s [HTTP: Anonymous, HTTPS] 3.3.3.3:8000>
    Found proxy: <Proxy DE 0.45s [SOCKS4, SOCKS5] 4.4.4.4:1080>

Advanced example
""""""""""""""""

.. code-block:: python

    import asyncio
    from proxybroker import Broker

    async def use_example(proxies):
        while True:
            proxy = await proxies.get()
            if proxy is None:
                break
            print('Found proxy: %s' % proxy)

    async def find_advanced_example(proxies, loop):
        broker = Broker(queue=proxies,
                        timeout=8,
                        attempts_conn=3,
                        max_concurrent_conn=200,
                        judges=['https://httpheader.net/', 'http://httpheader.net/'],
                        providers=['http://www.proxylists.net/', 'http://fineproxy.org/eng/'],
                        verify_ssl=False,
                        loop=loop)

        # only anonymous & high levels of anonymity for http protocol and high for others:
        types = [('HTTP', ('Anonymous', 'High')), 'HTTPS', 'SOCKS4', 'SOCKS5']
        countries = ['US', 'GB', 'DE']
        limit = 10

        await broker.find(types=types, countries=countries, limit=limit)

    if __name__ == '__main__':
        loop = asyncio.get_event_loop()
        proxies = asyncio.Queue(loop=loop)
        tasks = asyncio.gather(find_advanced_example(proxies, loop), use_example(proxies))
        loop.run_until_complete(tasks)

In this example we explicitly specify the parameters that directly affect on the speed of gathering and checking proxy (see `Broker parameters`_). In most cases it's redundant.

Usually we want to find:

* certain number of specific types proxy
* with a high level of anonymity
* and from specific countries. 

To do this, we pass parameters ``types``, ``countries`` and ``limit`` to the ``find`` method (see `Broker methods`_).

Note: We gather proxies from providers, check and send them to separate function, that can begin to work with proxies immediately without waiting for end of the search. You can start to use the proxies in a couple of seconds after the start of the search. And until the search is not stopped you will have more and more proxies.


Example #3: check proxies from your source
""""""""""""""""""""""""""""""""""""""""""

.. code-block:: python
    
    # ...
    data = '''10.0.0.1:80
              OK 10.0.0.2:   80 HTTP 200 OK 1.214
              10.0.0.3;80;SOCKS5 check date 21-01-02
              >>>10.0.0.4@80 HTTP HTTPS status OK
              ...'''

    await broker.find(data=data)
    # ...

You can have your source with proxies (it's usual .txt file). And all you want is to check all the proxies from it. To do this, simply pass it to the ``data`` argument.
Note: At the moment, information about the type of proxies in the raw data is ignored.

Example #4: only gather proxies (without check)
""""""""""""""""""""""""""""""""""""""""""""""""

.. code-block:: python

    # ...
    await broker.grab(countries=['US'], limit=100)
    # ...

If you need just to gather proxies without check. Use the ``grab`` method for it.
Note: The number of found proxies can reach over 40k.


API
---


Proxy properties
""""""""""""""""
.. table::

    +------------+------+-----------------------------------------+----------------------------------------------------------------------+
    |Property    | Type | Example                                 | Description                                                          |
    +============+======+=========================================+======================================================================+
    |host        | str  | '8.8.8.8'                               | The IP address of the proxy                                          |
    +------------+------+-----------------------------------------+----------------------------------------------------------------------+
    |port        | int  | 80                                      | The port of the proxy                                                |
    +------------+------+-----------------------------------------+----------------------------------------------------------------------+
    |types       | dict | {'HTTP': 'Anonymous', 'HTTPS': None}    | The dict of supported protocols and their levels of anonymity        |
    +------------+------+-----------------------------------------+----------------------------------------------------------------------+
    |geo         | dict | {'code': 'US', 'name': 'United States'} | The dict of ISO code and the full name of the country proxy location |
    +------------+------+-----------------------------------------+----------------------------------------------------------------------+
    |avgRespTime | str  | '1.11'                                  | The string with the average response time of proxy                   |
    +------------+------+-----------------------------------------+----------------------------------------------------------------------+


Broker parameters
"""""""""""""""""
.. table::

    +--------------------+----------+----------------------------+-------------------+--------------------------------------------------------------------------------------------------------------+
    | Parameter          | Required | Type                       | Default           | Description                                                                                                  |
    +====================+==========+============================+===================+==============================================================================================================+
    | queue              + Yes      | str                        |                   | Queue to which will be added proxies.                                                                        |
    +--------------------+----------+----------------------------+-------------------+--------------------------------------------------------------------------------------------------------------+
    | timeout            + No       | int                        | 8                 | Timeout is set to all the actions carried by the network. In seconds.                                        |
    +--------------------+----------+----------------------------+-------------------+--------------------------------------------------------------------------------------------------------------+
    | attempts_conn      | No       | int                        | 3                 | Limiting the maximum number of connection attempts.                                                          |
    +--------------------+----------+----------------------------+-------------------+--------------------------------------------------------------------------------------------------------------+
    |max_concurrent_conn | No       | int or asyncio.Semaphore() | 200               | Limiting the maximum number of concurrent connections (as a number, or have used in your program semaphore). |
    +--------------------+----------+----------------------------+-------------------+--------------------------------------------------------------------------------------------------------------+
    | providers          | No       | list of strings            | list of ~50 sites | The list of sites that distribute proxy lists (proxy providers).                                             |
    +--------------------+----------+----------------------------+-------------------+--------------------------------------------------------------------------------------------------------------+
    | judges             | No       | list of strings            | list of ~10 sites | The list of sites that show http-headers (proxy judges).                                                     |
    +--------------------+----------+----------------------------+-------------------+--------------------------------------------------------------------------------------------------------------+
    | verify_ssl         | No       | bool                       | False             | Check ssl certifications.                                                                                    |
    +--------------------+----------+----------------------------+-------------------+--------------------------------------------------------------------------------------------------------------+
    | loop               | No       | asyncio event loop         | None              | Event loop                                                                                                   |
    +--------------------+----------+----------------------------+-------------------+--------------------------------------------------------------------------------------------------------------+


Broker methods
""""""""""""""
.. table::

    +-----------------+---------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------+
    | Method          | Optional parameters                                                                               | Description                                                              |
    |                 +-------------+-------------------------------------------------------------------------------------+                                                                          |
    |                 | Parameter   | Description                                                                         |                                                                          |
    +=================+=============+=====================================================================================+==========================================================================+
    | find            | data        | As a source of proxies can be specified raw data. In this case,                     | Searching and checking proxies with requested parameters.                |
    |                 |             | search on the sites with a proxy does not happen. By default is empy.               |                                                                          |
    |                 +-------------+-------------------------------------------------------------------------------------+                                                                          |
    |                 | types       | The list of types (protocols) which must be checked.                                |                                                                          |
    |                 |             | Use a tuple if you want to specify the levels of anonymity: (Type, AnonLvl).        |                                                                          |
    |                 |             | By default, checks are enabled for all types at all levels of anonymity.            |                                                                          |
    |                 +-------------+-------------------------------------------------------------------------------------+                                                                          |
    |                 | countries   | List of ISO country codes, which must be located proxies.                           |                                                                          |
    |                 +-------------+-------------------------------------------------------------------------------------+                                                                          |
    |                 | limit       | Limit the search to a definite number of working proxies.                           |                                                                          |
    +-----------------+-------------+-------------------------------------------------------------------------------------+--------------------------------------------------------------------------+
    | grab            | countries   | List of ISO country codes, which must be located proxies.                           |  Only searching the proxies without checking their working.              |
    |                 +-------------+-------------------------------------------------------------------------------------+                                                                          |
    |                 | limit       | Limit the search to a definite number of working proxies.                           |                                                                          |
    +-----------------+-------------+-------------------------------------------------------------------------------------+--------------------------------------------------------------------------+
    | show_stats      | full        | If is False (by default) - will show a short version of stats (without proxieslog), | Limiting the maximum number of connection attempts.                      |
    |                 |             | if is True - show full version of stats (with proxies log).                         |                                                                          |
    +-----------------+-------------+-------------------------------------------------------------------------------------+--------------------------------------------------------------------------+


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


Contributing
------------

* Fork it: https://github.com/constverum/ProxyBroker/fork
* Create your feature branch: git checkout -b my-new-feature
* Commit your changes: git commit -am 'Add some feature'
* Push to the branch: git push origin my-new-feature
* Submit a pull request!


License
-------

Licensed under the Apache License, Version 2.0

*This product includes GeoLite2 data created by MaxMind, available from* `http://www.maxmind.com <http://www.maxmind.com>`_.
