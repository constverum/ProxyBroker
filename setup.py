import codecs
import re

from setuptools import setup

# https://packaging.python.org/en/latest/distributing/

with codecs.open('proxybroker/__init__.py', mode='r', encoding='utf-8') as f:
    INFO = dict(re.findall(r"__(\w+)__ = '([^']+)'", f.read(), re.MULTILINE))

with codecs.open('README.md', mode='r', encoding='utf-8') as f:
    INFO['long_description'] = f.read()

REQUIRES = [
    'aiohttp>=3.5.4',
    'aiodns>=2.0.0',
    'attrs==19.3.0',
    'maxminddb>=1.4.1',
    'cachetools==4.1.0',
]
SETUP_REQUIRES = ['pytest-runner>=4.4']
TEST_REQUIRES = [
    # 'black>=18.9-beta.0',
    'flake8>=3.7',
    'isort>=4.3',
    'pytest>=4.3',
    'pytest-asyncio>=0.10',
    'pytest-runner>=4.4',
    'pytest-isort>=0.3',
    'pytest-flake8>=1.0',
    'pytest-mock>=1.10.1',
]
PACKAGES = ['proxybroker', 'proxybroker.data']
PACKAGE_DATA = {'': ['LICENSE'], INFO['package']: ['data/*.mmdb']}

setup(
    name=INFO['package'],
    version=INFO['version'],
    description=INFO['short_description'],
    long_description=INFO['long_description'],
    author=INFO['author'],
    author_email=INFO['author_email'],
    license=INFO['license'],
    url=INFO['url'],
    install_requires=REQUIRES,
    setup_requires=SETUP_REQUIRES,
    tests_require=TEST_REQUIRES,
    packages=PACKAGES,
    package_data=PACKAGE_DATA,
    platforms='any',
    python_requires='>=3.5.3',
    entry_points={'console_scripts': ['proxybroker = proxybroker.cli:cli']},
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Operating System :: POSIX',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
        'Topic :: Internet :: Proxy Servers',
        'License :: OSI Approved :: Apache Software License',
    ],
    keywords=(
        'proxy finder grabber scraper parser graber scrapper checker '
        'broker async asynchronous http https connect socks socks4 socks5'
    ),
    zip_safe=False,
    test_suite='tests',
)
