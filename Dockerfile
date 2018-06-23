FROM python:3.6

RUN pip install proxybroker

CMD ["proxybroker", "find", "--types", "HTTP", "HTTPS", "--lvl", "High", "--countries", "US", "--strict", "-l", "10"]
