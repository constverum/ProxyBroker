# https://packaging.python.org/en/latest/distributing/
from setuptools import setup  # find_packages, find_package_data

PACKAGE = "proxybroker"
NAME = PACKAGE
DESCRIPTION = "[Finder/Grabber/Checker] Finds public proxies on multiple sources and concurrently checks them (type, anonymity, country). Supports HTTP(S) & SOCKS"
AUTHOR = "Constverum"
AUTHOR_EMAIL = "constverum@gmail.com"
URL = "https://github.com/constverum/ProxyBroker"
VERSION = __import__(PACKAGE).__version__

with open("README.rst", 'r') as f:
    longDescr = f.read()

packages = ['proxybroker',
            'proxybroker.data']
requires = ['aiodns', 'aiohttp', 'maxminddb']

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=longDescr,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    license="Apache License, Version 2.0",
    url=URL,
    packages=packages,
    install_requires=requires,
    package_data={NAME: ['LICENSE', 'data/*.txt', 'data/*.mmdb']},
    platforms="any",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.5",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Topic :: Internet :: Proxy Servers",
        "License :: OSI Approved :: Apache Software License",
    ],
    keywords='proxy finder grabber scrapper checker broker async asynchronous http https connect socks socks4 socks5',
    zip_safe=False,
    test_suite='tests',
)

# packages=find_packages(exclude=["tests.*", "tests"]),
# package_data=[PACKAGE],
# package_data=find_package_data(
#         PACKAGE,
#         only_in_packages=False),
# include_package_data=True,
# package_data = {
#     NAME: ['data/*.txt', 'data/*.mmdb', 'data/*.dat', 'LICENSE'],},
# data_files=[
#     ('/opt/local/myproject/etc', ['myproject/config/settings.py', 'myproject/config/other_settings.special']),
# ],
