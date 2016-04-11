if [[ ! -f "/opt/python3.5/bin/python3.5" ]]; then
    wget https://www.python.org/ftp/python/3.5.1/Python-3.5.1.tar.xz
    sudo apt-get update && sudo apt-get install tar xz-utils build-essential libssl-dev python3-pip -y
    tar xJf ./Python-3.5.1.tar.xz
    cd ./Python-3.5.1
    ./configure --prefix=/opt/python3.5 && \
    make && sudo make altinstall && ln -s /opt/python3.5/bin/python3.5 /usr/bin/python3.5
    sudo /opt/python3.5/bin/pip3.5 install aiohttp aiodns maxminddb && \
    cd .. && /opt/python3.5/bin/python3.5 server3.2.py;
else
    /opt/python3.5/bin/python3.5 server3.2.py;
fi
