#!/bin/bash

VERSION=v2.0.0-alpha4

docker build --pull -t bluet/proxybroker2 .
docker scan bluet/proxybroker2:latest

docker tag bluet/proxybroker2:latest bluet/proxybroker2:${VERSION}
git tag "${VERSION}" -a -m "proxybroker2 ${VERSION}"
git push
git push --tags

# Fixes busybox trigger error https://github.com/tonistiigi/xx/issues/36#issuecomment-926876468
docker run --privileged -it --rm tonistiigi/binfmt --install all

docker buildx create --use

while true; do
        read -p "Have I Updated VERSION Info? (Is current VERSION=${VERSION} ?) [y/N]" yn
        case $yn in
                [Yy]* ) docker buildx build -t bluet/proxybroker2:latest -t bluet/proxybroker2:${VERSION} --platform linux/amd64,linux/arm64/v8 --pull --push .; break;;
                [Nn]* ) exit;;
                * ) echo "";;
        esac
done


