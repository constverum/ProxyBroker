from setuptools import setup, find_packages, find_package_data

PACKAGE = "pyproxychecker"
NAME = PACKAGE
DESCRIPTION = "Asynchronous proxy checker. Support: HTTP, CONNECT(HTTPS), SOCKS4, SOCKS5"
AUTHOR = "Constverum"
AUTHOR_EMAIL = "constverum@gmail.com"
URL = "https://github.com/constverum/PyProxyChecker"
VERSION = __import__(PACKAGE).__version__

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=read("README.rst"),
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    license="Apache License, Version 2.0",
    url=URL,
    packages=find_packages(exclude=["tests.*", "tests"]),
    install_requires=[],
    platforms = "any",
    package_data=find_package_data(
            PACKAGE,
            only_in_packages=False),
    classifiers=[
        "Development Status :: 3 - Alpha"
        "Environment :: Console",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.5",
        "Operating System :: OS Independent",
        "Topic :: Internet :: Proxy Servers",
        "License :: OSI Approved :: Apache Software License",
    ],
    keywords='async asynchronous proxy checker http https connect socks socks4 socks5',
    zip_safe=False,
)
