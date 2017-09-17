"""CLI."""

import sys
import asyncio
import logging
import argparse

from . import __version__ as version
from .api import Broker


def create_parser():
    parser = argparse.ArgumentParser(
        prog='proxybroker',
        add_help=False,
        description='Proxy [Finder | Checker | Server]',
        epilog='''Run '%(prog)s <command> --help'
                  for more information on a command.
                  Suggestions and bug reports are greatly appreciated:
                  https://github.com/constverum/ProxyBroker/issues''')

    subparsers = parser.add_subparsers(
        dest='command',
        title='Commands',
        description='These are common commands used in various situations')
    parser_group = parser.add_argument_group(title='Options')
    add_broker_args(parser_group)
    add_help_arg(parser_group)

    fparser = subparsers.add_parser(
        'find',
        add_help=False,
        help='Find and check proxies',
        description='Find and check proxies with specified parameters')
    fparser_group = fparser.add_argument_group(title='Options')
    add_find_args(fparser_group)
    add_grab_args(fparser_group)
    add_limit_arg(fparser_group)
    add_outfile_arg(fparser_group)
    add_show_stats_arg(fparser_group)
    add_help_arg(fparser_group)

    gparser = subparsers.add_parser(
        'grab',
        add_help=False,
        help='Find proxies without a check',
        description='Find proxies without a check with specified parameters')
    gparser_group = gparser.add_argument_group(title='Options')
    add_grab_args(gparser_group)
    add_limit_arg(gparser_group)
    add_outfile_arg(gparser_group)
    add_show_stats_arg(gparser_group)
    add_help_arg(gparser_group)

    sparser = subparsers.add_parser(
        'serve',
        add_help=False,
        help='Run a local proxy server',
        description='''Run a local proxy server that distributes requests to
                       external proxies, which will be found on the
                       specified parameters''')
    add_serve_args(sparser.add_argument_group(title='Server options'))
    sparser_fgroup = sparser.add_argument_group(title='Find proxies options')
    add_find_args(sparser_fgroup)
    add_grab_args(sparser_fgroup)
    add_limit_arg(sparser_fgroup, 100, '''
        When will be found a requested number of working proxies,
        checking of new proxies will be lazily paused.
        See the documentation for more information''')
    add_help_arg(sparser.add_argument_group(title='Common options'))

    return parser


def add_broker_args(group):
    group.add_argument(
        '--max-conn',
        type=int,
        default=200,
        dest='max_conn',
        help='The maximum number of concurrent checks of proxies')
    group.add_argument(
        '--max-tries',
        type=int,
        default=3,
        dest='max_tries',
        help='The maximum number of attempts to check a proxy')
    group.add_argument(
        '--timeout', '-t',
        type=int,
        default=8,
        metavar='SECONDS',
        help='''Timeout of a request in seconds.
                The default value is 8 seconds''')
    group.add_argument(
        '--judge',
        action='append',
        dest='judges',
        help='Urls of pages that show HTTP headers and IP address')
    group.add_argument(
        '--provider',
        action='append',
        dest='providers',
        help='Urls of pages where to find proxies')
    group.add_argument(
        '--verify-ssl', '-ssl',
        dest='verify_ssl',
        action='store_true',
        help='Flag indicating whether to check the SSL certificates')
    group.add_argument(
        '--log',
        nargs='?',
        default=logging.CRITICAL,
        choices=['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level')
    group.add_argument(
        '--version', '-v',
        action='version',
        version='%(prog)s {v}'.format(v=version),
        help='Show program\'s version number and exit')


def add_find_args(group):
    group.add_argument(
        '--types',
        nargs='+',
        type=str.upper,
        required=True,
        choices=['HTTP', 'HTTPS', 'SOCKS4', 'SOCKS5',
                 'CONNECT:80', 'CONNECT:25'],
        help='Type(s) (protocols) that need to be check on support by proxy')
    group.add_argument(
        '--lvl',
        dest='anon_lvl',
        nargs='+',
        type=str.title,
        choices=['Transparent', 'Anonymous', 'High'],
        help='Level(s) of anonymity (for HTTP only). By default, any level')
    group.add_argument(
        '--data',
        type=argparse.FileType('r'),
        help='''Path to the file with proxies.
                If specified, used instead of providers''')
    group.add_argument(
        '--dnsbl',
        nargs='+',
        help='Spam databases for proxy checking')
    group.add_argument(
        '--post',
        action='store_true',
        help='''Flag indicating use POST instead of GET
                for requests when checking proxies''')
    group.add_argument(
        '--strict', '-s',
        action='store_true',
        help='''Flag indicating that anonymity levels of the
                types (protocols) supported by a proxy must
                be equal to the requested types and levels of anonymity''')


def add_grab_args(group):
    group.add_argument(
        '--countries', '-c',
        nargs='+',
        help='List of ISO country codes where should be located proxies')


def add_serve_args(group):
    group.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help='Host of local proxy server')
    group.add_argument(
        '--port',
        type=int,
        default=8888,
        help='Port of local proxy server')
    group.add_argument(
        '--max-tries',
        type=int,
        dest='srv_max_tries',
        help='''The maximum number of attempts to handle an incoming request.
                If not specified, will be used the value passed to the %(prog)s
                command''')
    group.add_argument(
        '--min-req-proxy',
        type=int,
        default=5,
        dest='min_req_proxy',
        help='''The minimum number of processed requests to decide
                whether to use it further or reject''')
    group.add_argument(
        '--max-error-rate',
        type=float,
        default=0.5,
        dest='max_error_rate',
        help='''The maximum percentage of requests that ended
                with an error. For example: 0.5 = 50%%''')
    group.add_argument(
        '--max-resp-time',
        type=int,
        default=8,
        dest='max_resp_time',
        metavar='SECONDS',
        help='''The maximum response time in seconds. If proxy.avg_resp_time exceeds
                this value, proxy will be rejected.
                The default value is 8 seconds''')
    group.add_argument(
        '--prefer-connect',
        action='store_true',
        dest='prefer_connect',
        help='''Flag that indicates whether to use
                the CONNECT method if possible''')
    group.add_argument(
        '--http-allowed-codes',
        nargs='+',
        type=int,
        dest='http_allowed_codes',
        help='Acceptable HTTP codes returned by proxy on requests')
    group.add_argument(
        '--backlog',
        type=int,
        default=100,
        help='The maximum number of queued connections passed to listen')


def add_limit_arg(group, _def=0,
                  _help='The maximum number of working proxies'):
    group.add_argument(
        '--limit', '-l',
        type=int,
        default=_def,
        help=_help)


def add_outfile_arg(group):
    group.add_argument(
        '--outfile', '-o',
        type=argparse.FileType('w'),
        default=sys.stdout,
        help='Save found proxies to file. By default, output to console')


def add_show_stats_arg(group):
    group.add_argument(
        '--show-stats',
        dest='show_stats',
        action='store_true',
        help='Flag indicating whether to print verbose stats')


def add_help_arg(group):
    group.add_argument(
        '--help', '-h',
        action='help',
        help='Show this help message and exit')


async def handle(proxies, outfile):
    # TODO: add custom format
    while True:
        proxy = await proxies.get()
        if proxy is None:
            break
        outfile.write('%r\n' % proxy)


def cli(args=sys.argv[1:]):
    parser = create_parser()
    ns = parser.parse_args(args)

    if not ns.command:
        parser.print_help()
        return

    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='[%H:%M:%S]', level=ns.log)

    if hasattr(ns, 'anon_lvl') and 'HTTP' in ns.types:
        ns.types.remove('HTTP')
        ns.types.append(('HTTP', ns.anon_lvl))

    loop = asyncio.get_event_loop()
    proxies = asyncio.Queue(loop=loop)
    broker = Broker(
        proxies, max_conn=ns.max_conn, max_tries=ns.max_tries,
        timeout=ns.timeout, judges=ns.judges, providers=ns.providers,
        verify_ssl=ns.verify_ssl, loop=loop)

    if ns.command in ('find', 'grab'):
        tasks = [handle(proxies, outfile=ns.outfile)]
    else:
        tasks = []

    if ns.command == 'find':
        tasks.append(broker.find(
            data=ns.data, types=ns.types, countries=ns.countries,
            post=ns.post, strict=ns.strict, dnsbl=ns.dnsbl, limit=ns.limit))
    elif ns.command == 'grab':
        tasks.append(broker.grab(countries=ns.countries, limit=ns.limit))
    elif ns.command == 'serve':
        broker.serve(
            host=ns.host, port=ns.port, limit=ns.limit,
            min_req_proxy=ns.min_req_proxy, max_error_rate=ns.max_error_rate,
            max_resp_time=ns.max_resp_time, prefer_connect=ns.prefer_connect,
            http_allowed_codes=ns.http_allowed_codes, backlog=ns.backlog,
            data=ns.data, types=ns.types, countries=ns.countries, post=ns.post,
            strict=ns.strict, dnsbl=ns.dnsbl)
        print('Server started at http://%s:%d' % (ns.host, ns.port))

    try:
        if tasks:
            loop.run_until_complete(asyncio.gather(*tasks, loop=loop))
            if ns.show_stats:
                broker.show_stats(verbose=True)
        else:
            loop.run_forever()
    except KeyboardInterrupt:
        broker.stop()
    finally:
        loop.stop()
        loop.close()
