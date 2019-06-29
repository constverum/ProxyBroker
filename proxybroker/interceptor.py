from http_parser.parser import HttpParser
from OpenSSL import crypto
from socket import gethostname
import traceback
import asyncio
import aiohttp
import time
import ssl
import os

from .utils import log
from .errors import (
    BadResponseError,
    BadStatusError,
    ErrorOnStream,
    ProxyConnError,
    ProxyEmptyRecvError,
    ProxyRecvError,
    ProxySendError,
    ProxyTimeoutError,
)


def create_self_signed_cert():
    """ Generates self signed SSL certificate. """

    # Creates key pair.
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 1024)

    # Creates self-signed certificate.
    cert = crypto.X509()
    cert.get_subject().C = "US"
    cert.get_subject().ST = "New York"
    cert.get_subject().L = "New York"
    cert.get_subject().O = "."
    cert.get_subject().OU = "."
    cert.get_subject().CN = gethostname()
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, "sha1")

    if not os.path.exists("ssl"):
        os.makedirs("ssl")

    with open("ssl/server.crt", "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))

    with open("ssl/server.key", "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))


class EmulatedClient(object):
    """ Class for emulating the client to the server. """

    def __init__(
        self,
        loop,
        timeout,
        max_tries,
        prefer_connect,
        http_allowed_codes,
        proxy_pool,
        resolver,
        using_ssl,
    ):
        # Setting the class variables.
        self._loop = loop
        self._timeout = timeout
        self._max_tries = max_tries
        self._prefer_connect = prefer_connect
        self._http_allowed_codes = http_allowed_codes
        self._proxy_pool = proxy_pool
        self._resolver = resolver
        self._using_ssl = using_ssl

        # Last response gathered to return back to client.
        self._last_resp = None

    async def connect(self, data):

        scheme = 'HTTPS' if self._using_ssl else 'HTTP'

        for attempt in range(self._max_tries):
            # Setting intial variables for proxy filtering (if needed).
            stime, err = 0, None

            # Gets a proxy from the Proxy pool.
            proxy = await self._proxy_pool.get(scheme)

            # Parses the incoming data.
            http_parser = HttpParser()
            http_parser.execute(data, len(data))
            host = http_parser.get_wsgi_environ()['HTTP_HOST']
            uri = http_parser.get_wsgi_environ()['RAW_URI']

            # Sets the proper URL client is trying to reach.
            if self._using_ssl:
                url = f"https://{host}:{uri}"
            else:
                url = uri

            try:
                await proxy.connect()

                log.info(
                    f"Attempting to reach {host} for the {attempt} time, with proxy {proxy.host}:{proxy.port}."
                )

                # Begins the streaming between the client and the proxy.
                resp = asyncio.create_task(self.stream(proxy, data, url))
                await asyncio.wait_for(resp, timeout=self._timeout)

                # If the response exists, return it.
                if resp:
                    log.info(
                        f"Successfully reached host {host}. Returning data to client."
                    )
                    return resp.result()

                # Saves the proxy time.
                stime = time.time()

            except asyncio.TimeoutError:
                log.debug(
                    f"Timeout error with proxy {proxy.host}:{proxy.port}. Flagging from pool."
                )
                continue
            except ErrorOnStream as e:
                if "Proxy error" in e:
                    log.debug(
                        f"Issue with proxy {proxy.host}:{proxy.port}. Flagging from pool."
                    )

                if "Response error" in e:
                    log.debug(f"Issue with getting the response.")
                continue
            except Exception:
                # Prints the traceback if the exception is not caught.
                traceback.print_exc()
                continue
            finally:
                proxy.log(data.decode(), stime, err=err)
                proxy.close()
                self._proxy_pool.put(proxy)

        # Here if all the attempts were exhausted without success.
        return self._last_resp

    async def stream(self, proxy, data, url):
        try:
            # Retrieves the destination server data.
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, proxy=f"http://{proxy.host}:{proxy.port}", ssl=False
                ) as response:
                    status = response.status
                    reason = response.reason
                    headers = response.headers
                    response = await response.read()

            # Creating the response.
            resp = f"HTTP/1.1 {status} {reason}\r\n".encode("latin-1")
            for header in headers:
                resp += f"{header}: {headers[header]}\r\n".encode("latin-1")
            resp += b"\r\n" + response

            # Does checks, and returns response.
            if resp and status in self._http_allowed_codes:
                return resp
            else:
                self._last_resp = resp
                raise ErrorOnStream("Response is invalid.")
        except (
            ProxyTimeoutError,
            ProxyConnError,
            ProxyRecvError,
            ProxySendError,
            ProxyEmptyRecvError,
        ) as e:
            raise ErrorOnStream(f"Proxy error. {e}")
        except (
            asyncio.TimeoutError,
            ConnectionResetError,
            OSError,
            BadStatusError,
            BadResponseError,
        ) as e:
            raise ErrorOnStream(f"Response error. {e}")

    def check_proxy_protocol(self, proxy, scheme):
        if scheme == 'HTTP':
            if self._prefer_connect and ('CONNECT:80' in proxy.types):
                proto = 'CONNECT:80'
            else:
                relevant = {
                    'HTTP',
                    'CONNECT:80',
                    'SOCKS4',
                    'SOCKS5',
                } & proxy.types.keys()
                proto = relevant.pop()
        else:  # HTTPS
            relevant = {'HTTPS', 'SOCKS4', 'SOCKS5'} & proxy.types.keys()
            proto = relevant.pop()

        return proto


class HTTP(asyncio.Protocol):
    def __init__(
        self,
        loop,
        timeout,
        max_tries,
        prefer_connect,
        http_allowed_codes,
        proxy_pool,
        resolver,
        using_tls,
    ):

        # Setting the class variables.
        self._loop = loop
        self._timeout = timeout
        self._max_tries = max_tries
        self._prefer_connect = prefer_connect
        self._http_allowed_codes = http_allowed_codes
        self._proxy_pool = proxy_pool
        self._resolver = resolver
        self._using_ssl = using_tls

        # Initiates the HttpParser object.
        self.http_parser = HttpParser()

    def connection_made(self, transport):
        """ Begins connection with the transporter. """
        self.transport = transport

        # Getting the client address and port number.
        self.client, self.client_ip = self.transport.get_extra_info("peername")

    def data_received(self, data):
        """ Receives unencrypted client data, and begin the emulated client process. """

        self._loop.create_task(self.reply(data))

    async def reply(self, data):
        """ Receives reply from destination server through the Emulated Client. """

        # Starting our emulated client. This object talks with the server.
        self.emulated_client = EmulatedClient(
            loop=self._loop,
            timeout=self._timeout,
            max_tries=self._max_tries,
            prefer_connect=self._prefer_connect,
            http_allowed_codes=self._http_allowed_codes,
            proxy_pool=self._proxy_pool,
            resolver=self._resolver,
            using_ssl=self._using_ssl,
        )

        # Gathering the reply from the emulated client.
        reply = (await asyncio.gather(self.emulated_client.connect(data)))[0]

        # Writing back to the client.
        self.transport.write(reply)

        # Closing connection with the client.
        self.transport.close()
        self.info(
            f"Closing connection with client {self.client}:{self.client_ip}."
        )


class Interceptor(asyncio.Protocol):
    """ Class for intercepting client communication.

        Notes:
            To accomplish a proper man-in-the-middle attack with TLS capability,
            the man-in-the-middle must be the one sending the original request to
            the server. With the emulated client we are changing the typical structure:

                client <-> server

            To one that looks like so:

                client <-> mitm (server) <-> mitm (emulated client) <-> server

            Where we then reply back to the client with the response the emulated client
            retrieved from the server on behalf of the client.
    """

    def __init__(
        self,
        loop,
        timeout,
        max_tries,
        prefer_connect,
        http_allowed_codes,
        proxy_pool,
        resolver,
    ):

        # Setting the class variables.
        self._loop = loop
        self._timeout = timeout
        self._max_tries = max_tries
        self._prefer_connect = prefer_connect
        self._http_allowed_codes = http_allowed_codes
        self._proxy_pool = proxy_pool
        self._resolver = resolver

        # Creates the TLS flag.
        self.using_tls = False

        # Initiates the HttpParser object.
        self.http_parser = HttpParser()

        # Initiating our HTTP transport with the emulated client.
        self.HTTP_Protocol = HTTP(
            loop=self._loop,
            timeout=self._timeout,
            max_tries=self._max_tries,
            prefer_connect=self._prefer_connect,
            http_allowed_codes=self._http_allowed_codes,
            proxy_pool=self._proxy_pool,
            resolver=self._resolver,
            using_tls=self.using_tls,
        )

        # We only initialize our HTTPS_Protocol when we get a CONNECT statement.
        self.HTTPS_Protocol = None

    def connection_made(self, transport):
        """ Called when client makes initial connection to the server. Receives a transporting object from the client. """
        # Setting our transport object.
        self.transport = transport

        # Getting the client address and port number.
        self.client, self.client_ip = self.transport.get_extra_info("peername")

    def data_received(self, data):
        """
            Called when a connected client sends data to the server; HTTP or HTTPS requests.

            Note:
                This method is called multiple times during a typical TLS/SSL connection with a client.
                    1. Client sends server message to connect; "CONNECT."
                    2. Server replies with "OK" and begins handshake.
                    3. Client sends server encrypted HTTP requests; "GET", "POST", etc.
        """

        # Parses the data the client has sent to the server.
        self.http_parser.execute(data, len(data))

        if (
            self.http_parser.get_method() == "CONNECT"
            and self.using_tls == False
        ):

            # Logging we are using HTTPS.
            log.info(
                f"Connected with client {self.client}:{self.client_ip} with HTTPS."
            )

            # Generating the SSL certificate and keys if needed.
            if not os.path.exists("ssl"):
                create_self_signed_cert()
                log.info(
                    "Generating SSL certificate to communicate with client."
                )

            # Sets TLS flag as on -- after exiting this if statement, the data will be encrypted.
            self.using_tls = True

            # Loading the protocol certificates.
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            ssl_context.load_cert_chain("ssl/server.crt", "ssl/server.key")

            # Initialize the HTTPS_Protocol.
            self.HTTPS_Protocol = asyncio.sslproto.SSLProtocol(
                loop=self._loop,
                app_protocol=HTTP(
                    loop=self._loop,
                    timeout=self._timeout,
                    max_tries=self._max_tries,
                    prefer_connect=self._prefer_connect,
                    http_allowed_codes=self._http_allowed_codes,
                    proxy_pool=self._proxy_pool,
                    resolver=self._resolver,
                    using_tls=self.using_tls,
                ),
                sslcontext=ssl_context,
                waiter=None,
                server_side=True,
            )

            # Replies to the client that the server has connected.
            self.transport.write(b"HTTP/1.1 200 OK\r\n\r\n")
            # Sending initial CONNECT request over for handshake.
            self.HTTPS_Protocol.data_received(data)
            # Does a TLS/SSL handshake with the client.
            self.HTTPS_Protocol.connection_made(self.transport)
        elif self.using_tls:
            # With HTTPS protocol enabled, receives encrypted data from the client (gets decrypted by data_received).
            self.HTTPS_Protocol.data_received(data)
        else:
            # Logging we are using HTTP.
            log.info(
                f"Connected with client {self.client}:{self.client_ip} with HTTP."
            )

            # Receives standard, non-encrypted data from the client (TLS/SSL is off).
            self.HTTP_Protocol.connection_made(self.transport)
            self.HTTP_Protocol.data_received(data)
