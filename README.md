ProxyBroker
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-1-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->
===========

![image](https://img.shields.io/pypi/v/proxybroker.svg?style=flat-square%0A%20:target:%20https://pypi.python.org/pypi/proxybroker/)
![image](https://img.shields.io/travis/constverum/ProxyBroker.svg?style=flat-square%0A%20:target:%20https://travis-ci.org/constverum/ProxyBroker)
![image](https://img.shields.io/pypi/wheel/proxybroker.svg?style=flat-square%0A%20:target:%20https://pypi.python.org/pypi/proxybroker/)
![image](https://img.shields.io/pypi/pyversions/proxybroker.svg?style=flat-square%0A%20:target:%20https://pypi.python.org/pypi/proxybroker/)
![image](https://img.shields.io/pypi/l/proxybroker.svg?style=flat-square%0A%20:target:%20https://pypi.python.org/pypi/proxybroker/)

ProxyBroker is an open source tool that asynchronously finds public proxies from multiple sources and concurrently checks them.

![image](https://raw.githubusercontent.com/constverum/ProxyBroker/master/docs/source/_static/index_find_example.gif)

Features
--------

-   Finds more than 7000 working proxies from \~50 sources.
-   Support protocols: HTTP(S), SOCKS4/5. Also CONNECT method to ports 80 and 23 (SMTP).
-   Proxies may be filtered by type, anonymity level, response time, country and status in DNSBL.
-   Work as a proxy server that distributes incoming requests to external proxies. With automatic proxy rotation.
-   All proxies are checked to support Cookies and Referer (and POST requests if required).
-   Automatically removes duplicate proxies.
-   Is asynchronous.

Docker
------
Docker Hub https://hub.docker.com/r/bluet/proxybroker2

```
$ docker run --rm bluet/proxybroker2 --help
  usage: proxybroker [--max-conn MAX_CONN] [--max-tries MAX_TRIES]
                     [--timeout SECONDS] [--judge JUDGES] [--provider PROVIDERS]
                     [--verify-ssl]
                     [--log [{NOTSET,DEBUG,INFO,WARNING,ERROR,CRITICAL}]]
                     [--min-queue MINIMUM_PROXIES_IN_QUEUE]
                     [--version] [--help]
                     {find,grab,serve,update-geo} ...

  Proxy [Finder | Checker | Server]

  Commands:
    These are common commands used in various situations

    {find,grab,serve,update-geo}
      find                Find and check proxies
      grab                Find proxies without a check
      serve               Run a local proxy server
      update-geo          Download and use a detailed GeoIP database

  Options:
    --max-conn MAX_CONN   The maximum number of concurrent checks of proxies
    --max-tries MAX_TRIES
                          The maximum number of attempts to check a proxy
    --timeout SECONDS, -t SECONDS
                          Timeout of a request in seconds. The default value is
                          8 seconds
    --judge JUDGES        Urls of pages that show HTTP headers and IP address
    --provider PROVIDERS  Urls of pages where to find proxies
    --verify-ssl, -ssl    Flag indicating whether to check the SSL certificates
    --min-queue MINIMUM_PROXIES_IN_QUEUE   The minimum number of proxies in the queue for checking connectivity
    --log [{NOTSET,DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                          Logging level
    --version, -v         Show program's version number and exit
    --help, -h            Show this help message and exit

  Run 'proxybroker <command> --help' for more information on a command.
  Suggestions and bug reports are greatly appreciated:
  <https://github.com/bluet/proxybroker2/issues>

```


Requirements
------------

-   Python **3.5**, **3.6** or **3.7**. (need help on porting to 3.8+)
-   [aiohttp](https://pypi.python.org/pypi/aiohttp)
-   [aiodns](https://pypi.python.org/pypi/aiodns)
-   [maxminddb](https://pypi.python.org/pypi/maxminddb)

Installation
------------

To install last stable release from pypi:

``` {.sourceCode .bash}
$ pip install proxybroker
```

The latest development version can be installed directly from GitHub:

``` {.sourceCode .bash}
$ pip install -U git+https://github.com/bluet/proxybroker2.git
```

Usage
-----

### CLI Examples

#### Find

Find and show 10 HTTP(S) proxies from United States with the high level of anonymity:

``` {.sourceCode .bash}
$ proxybroker find --types HTTP HTTPS --lvl High --countries US --strict -l 10
```

![image](https://raw.githubusercontent.com/constverum/ProxyBroker/master/docs/source/_static/cli_find_example.gif)

#### Grab

Find and save to a file 10 US proxies (without a check):

``` {.sourceCode .bash}
$ proxybroker grab --countries US --limit 10 --outfile ./proxies.txt
```

![image](https://raw.githubusercontent.com/constverum/ProxyBroker/master/docs/source/_static/cli_grab_example.gif)

#### Serve

Run a local proxy server that distributes incoming requests to a pool of found HTTP(S) proxies with the high level of anonymity:

``` {.sourceCode .bash}
$ proxybroker serve --host 127.0.0.1 --port 8888 --types HTTP HTTPS --lvl High --min-queue 5
```

![image](https://raw.githubusercontent.com/constverum/ProxyBroker/master/docs/source/_static/cli_serve_example.gif)

Run `proxybroker --help` for more information on the options available.
Run `proxybroker <command> --help` for more information on a command.

### Basic code example

Find and show 10 working HTTP(S) proxies:

``` {.sourceCode .python}
import asyncio
from proxybroker import Broker

async def show(proxies):
    while True:
        proxy = await proxies.get()
        if proxy is None: break
        print('Found proxy: %s' % proxy)

proxies = asyncio.Queue()
broker = Broker(proxies)
tasks = asyncio.gather(
    broker.find(types=['HTTP', 'HTTPS'], limit=10),
    show(proxies))

loop = asyncio.get_event_loop()
loop.run_until_complete(tasks)
```

[More examples](https://proxybroker.readthedocs.io/en/latest/examples.html).

### Proxy information per requests
#### HTTP
Check `X-Proxy-Info` header in response.
```
$ http_proxy=http://127.0.0.1:8888 https_proxy=http://127.0.0.1:8888 curl -v http://httpbin.org/get
*   Trying 127.0.0.1...
* TCP_NODELAY set
* Connected to 127.0.0.1 (127.0.0.1) port 8888 (#0)
> GET http://httpbin.org/get HTTP/1.1
> Host: httpbin.org
> User-Agent: curl/7.58.0
> Accept: */*
> Proxy-Connection: Keep-Alive
>
< HTTP/1.1 200 OK
< X-Proxy-Info: 174.138.42.112:8080
< Date: Mon, 04 May 2020 03:39:40 GMT
< Content-Type: application/json
< Content-Length: 304
< Server: gunicorn/19.9.0
< Access-Control-Allow-Origin: *
< Access-Control-Allow-Credentials: true
< X-Cache: MISS from ADM-MANAGER
< X-Cache-Lookup: MISS from ADM-MANAGER:880
< Connection: keep-alive
<
{
  "args": {},
  "headers": {
    "Accept": "*/*",
    "Cache-Control": "max-age=259200",
    "Host": "httpbin.org",
    "User-Agent": "curl/7.58.0",
    "X-Amzn-Trace-Id": "Root=1-5eaf8e7c-6a1162a1387a1743a49063f4"
  },
  "origin": "...",
  "url": "http://httpbin.org/get"
}
* Connection #0 to host 127.0.0.1 left intact
```

#### HTTPS
We are not able to modify HTTPS traffic to inject custom header once they start being encrypted. A `X-Proxy-Info` will be sent to client after `HTTP/1.1 200 Connection established` but not sure how clients can read it.
```
(env) bluet@ocisly:~/workspace/proxybroker2$ http_proxy=http://127.0.0.1:8888 https_proxy=http://127.0.0.1:8888 curl -v https://httpbin.org/get
*   Trying 127.0.0.1...
* TCP_NODELAY set
* Connected to 127.0.0.1 (127.0.0.1) port 8888 (#0)
* allocate connect buffer!
* Establish HTTP proxy tunnel to httpbin.org:443
> CONNECT httpbin.org:443 HTTP/1.1
> Host: httpbin.org:443
> User-Agent: curl/7.58.0
> Proxy-Connection: Keep-Alive
>
< HTTP/1.1 200 Connection established
< X-Proxy-Info: 207.148.22.139:8080
<
* Proxy replied 200 to CONNECT request
* CONNECT phase completed!
* ALPN, offering h2
* ALPN, offering http/1.1
* successfully set certificate verify locations:
...
*  SSL certificate verify ok.
* Using HTTP2, server supports multi-use
* Connection state changed (HTTP/2 confirmed)
* Copying HTTP/2 data in stream buffer to connection buffer after upgrade: len=0
* Using Stream ID: 1 (easy handle 0x5560b2e93580)
> GET /get HTTP/2
> Host: httpbin.org
> User-Agent: curl/7.58.0
> Accept: */*
>
* Connection state changed (MAX_CONCURRENT_STREAMS updated)!
< HTTP/2 200
< date: Mon, 04 May 2020 03:39:35 GMT
< content-type: application/json
< content-length: 256
< server: gunicorn/19.9.0
< access-control-allow-origin: *
< access-control-allow-credentials: true
<
{
  "args": {},
  "headers": {
    "Accept": "*/*",
    "Host": "httpbin.org",
    "User-Agent": "curl/7.58.0",
    "X-Amzn-Trace-Id": "Root=1-5eaf8e77-efcb353b0983ad6a90f8bdcd"
  },
  "origin": "...",
  "url": "https://httpbin.org/get"
}
* Connection #0 to host 127.0.0.1 left intact
```

### HTTP API
#### Get info of proxy been used for retrieving specific url
For HTTP, it's easy.
```
$ http_proxy=http://127.0.0.1:8888 https_proxy=http://127.0.0.1:8888 curl -v http://proxycontrol/api/history/url:http://httpbin.org/get
*   Trying 127.0.0.1...
* TCP_NODELAY set
* Connected to 127.0.0.1 (127.0.0.1) port 8888 (#0)
> GET http://proxycontrol/api/history/url:http://httpbin.org/get HTTP/1.1
> Host: proxycontrol
> User-Agent: curl/7.58.0
> Accept: */*
> Proxy-Connection: Keep-Alive
>
< HTTP/1.1 200 OK
< Content-Type: application/json
< Content-Length: 34
< Access-Control-Allow-Origin: *
< Access-Control-Allow-Credentials: true
<
{"proxy": "..."}
```

For HTTPS, we're not able to know encrypted payload (request), so only hostname can be used.
```
$ http_proxy=http://127.0.0.1:8888 https_proxy=http://127.0.0.1:8888 curl -v http://proxycontrol/api/history/url:httpbin.org:443
*   Trying 127.0.0.1...
* TCP_NODELAY set
* Connected to 127.0.0.1 (127.0.0.1) port 8888 (#0)
> GET http://proxycontrol/api/history/url:httpbin.org:443 HTTP/1.1
> Host: proxycontrol
> User-Agent: curl/7.58.0
> Accept: */*
> Proxy-Connection: Keep-Alive
>
< HTTP/1.1 200 OK
< Content-Type: application/json
< Content-Length: 34
< Access-Control-Allow-Origin: *
< Access-Control-Allow-Credentials: true
<
{"proxy": "..."}
* Connection #0 to host 127.0.0.1 left intact
```

#### Remove specific proxy from queue
```
$ http_proxy=http://127.0.0.1:8888 https_proxy=http://127.0.0.1:8888 curl -v http://proxycontrol/api/remove/PROXY_IP:PROXY_PORT
*   Trying 127.0.0.1...
* TCP_NODELAY set
* Connected to 127.0.0.1 (127.0.0.1) port 8888 (#0)
> GET http://proxycontrol/api/remove/... HTTP/1.1
> Host: proxycontrol
> User-Agent: curl/7.58.0
> Accept: */*
> Proxy-Connection: Keep-Alive
>
< HTTP/1.1 204 No Content
<
* Connection #0 to host 127.0.0.1 left intact
```

Documentation
-------------

<https://proxybroker.readthedocs.io/>

TODO
----

-   Check the ping, response time and speed of data transfer
-   Check site access (Google, Twitter, etc) and even your own custom URL's
-   Information about uptime
-   Checksum of data returned
-   Support for proxy authentication
-   Finding outgoing IP for cascading proxy
-   The ability to specify the address of the proxy without port (try to connect on defaulted ports)

Contributing
------------

-   Fork it: <https://github.com/bluet/proxybroker2/fork>
-   Create your feature branch: `git checkout -b my-new-feature`
-   Commit your changes: `git commit -am 'Add some feature'`
-   Push to the branch: `git push origin my-new-feature`
-   Submit a pull request!

License
-------

Licensed under the Apache License, Version 2.0

*This product includes GeoLite2 data created by MaxMind, available from* [<http://www.maxmind.com>](http://www.maxmind.com).

Refs
----

-   <https://github.com/constverum/ProxyBroker/pull/161>
-   <https://github.com/davidsarkany/docker-ProxyBroker>

## Contributors ✨

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tr>
    <td align="center"><a href="https://github.com/a5r0n"><img src="https://avatars.githubusercontent.com/u/32464596?v=4?s=100" width="100px;" alt=""/><br /><sub><b>a5r0n</b></sub></a><br /><a href="https://github.com/bluet/proxybroker2/commits?author=a5r0n" title="Code">💻</a></td>
    <td align="center"><a href="https://afun.tw"><img src="https://avatars.githubusercontent.com/u/4820492?v=4?s=100" width="100px;" alt=""/><br /><sub><b>C.M. Yang</b></sub></a><br /><a href="https://github.com/bluet/proxybroker2/commits?author=afunTW" title="Code">💻</a> <a href="#ideas-afunTW" title="Ideas, Planning, & Feedback">🤔</a> <a href="https://github.com/bluet/proxybroker2/pulls?q=is%3Apr+reviewed-by%3AafunTW" title="Reviewed Pull Requests">👀</a></td>
    <td align="center"><a href="http://ivanvillareal.com"><img src="https://avatars.githubusercontent.com/u/190708?v=4?s=100" width="100px;" alt=""/><br /><sub><b>Ivan Villareal</b></sub></a><br /><a href="https://github.com/bluet/proxybroker2/commits?author=ivaano" title="Code">💻</a></td>
    <td align="center"><a href="https://github.com/quancore"><img src="https://avatars.githubusercontent.com/u/15036825?v=4?s=100" width="100px;" alt=""/><br /><sub><b>Quancore</b></sub></a><br /><a href="https://github.com/bluet/proxybroker2/commits?author=quancore" title="Code">💻</a></td>
    <td align="center"><a href="https://github.com/synchronizing"><img src="https://avatars.githubusercontent.com/u/2829082?v=4?s=100" width="100px;" alt=""/><br /><sub><b>Felipe</b></sub></a><br /><a href="#ideas-synchronizing" title="Ideas, Planning, & Feedback">🤔</a></td>
    <td align="center"><a href="https://www.vincentinttsh.tw/"><img src="https://avatars.githubusercontent.com/u/14941597?v=4?s=100" width="100px;" alt=""/><br /><sub><b>vincentinttsh</b></sub></a><br /><a href="https://github.com/bluet/proxybroker2/commits?author=vincentinttsh" title="Code">💻</a> <a href="https://github.com/bluet/proxybroker2/pulls?q=is%3Apr+reviewed-by%3Avincentinttsh" title="Reviewed Pull Requests">👀</a></td>
  </tr>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!