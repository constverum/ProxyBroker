FROM python:3.10-alpine
WORKDIR /app
ADD . /app/
RUN apk --no-cache add --update \
    gcc musl-dev git ca-certificates libffi-dev openssl \
    && pip install . \
    && rm -rf /var/cache/apk/* \
    && rm -rf /tmp/*
ENTRYPOINT ["proxybroker"]
