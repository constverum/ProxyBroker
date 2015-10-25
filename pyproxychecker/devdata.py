import pprint
from collections import defaultdict, Counter

def test(s):
    proxies = s.get_good_proxies()
    d = dict(
        SOCKS5=['76.124.41.9'],
        SOCKS4=['41.60.130.36', '77.242.22.254', '82.208.95.64', '110.169.152.251', '119.47.91.113', '180.250.159.19', '187.210.37.36', '202.22.195.197', '219.157.77.102'],
        HTTPS=['5.39.81.72', '41.222.57.14', '54.174.168.237', '54.207.45.19', '62.204.241.146', '69.168.242.44', '69.168.255.85', '83.241.46.175', '94.23.200.49', '95.109.117.232', '120.195.193.109', '120.195.195.36', '120.195.199.85', '120.195.200.30', '120.195.201.165', '120.195.203.213', '120.195.205.116', '120.195.205.48', '120.195.206.63', '120.195.207.199', '152.26.69.30', '152.26.69.31', '152.26.69.32', '152.26.69.33', '152.26.69.36', '152.26.69.39', '152.26.69.40', '152.26.69.41', '152.26.69.42', '152.26.69.45', '152.231.45.136', '187.18.122.211', '192.99.20.92', '193.37.152.186', '198.100.148.75', '202.21.176.108', '212.119.242.68', '213.184.225.225', '218.92.227.170', '219.92.17.54'],
        HTTP=['5.39.81.72', '41.222.57.14', '54.207.45.19', '60.191.168.43', '60.191.174.13', '61.75.2.124', '62.204.241.146', '69.168.242.44', '69.168.255.85', '83.241.46.175', '94.23.200.49', '95.109.117.232', '106.186.114.239', '118.144.156.2', '120.195.193.109', '120.195.195.36', '120.195.199.85', '120.195.200.30', '120.195.201.165', '120.195.203.213', '120.195.205.116', '120.195.205.48', '120.195.206.63', '120.195.207.199', '152.231.45.136', '152.26.69.30', '152.26.69.31', '152.26.69.32', '152.26.69.33', '152.26.69.36', '152.26.69.39', '152.26.69.40', '152.26.69.41', '152.26.69.42', '152.26.69.45', '187.18.122.211', '190.15.192.120', '192.99.20.92', '193.37.152.186', '198.100.148.75', '202.21.176.108', '210.51.48.206', '212.119.242.68', '213.184.225.225', '218.76.76.11', '218.92.227.170', '219.92.17.54', '221.214.166.181', '222.243.16.44'])
    anon_lvl = {'41.222.57.14': 'Transparent',
                '54.207.45.19': 'Anonymous',
                '60.191.174.13': 'Transparent',
                '61.75.2.124': 'Transparent',
                '69.168.242.44': 'High',
                '69.168.255.85': 'High',
                '94.23.200.49': 'Transparent',
                '95.109.117.232': 'Transparent',
                '118.144.156.2': 'Transparent',
                '120.195.193.109': 'High',
                '120.195.195.36': 'High',
                '120.195.199.85': 'High',
                '120.195.200.30': 'High',
                '120.195.201.165': 'High',
                '120.195.203.213': 'High',
                '120.195.205.116': 'High',
                '120.195.205.48': 'High',
                '120.195.206.63': 'High',
                '120.195.207.199': 'High',
                '152.231.45.136': 'Transparent',
                '152.26.69.30': 'Anonymous',
                '152.26.69.31': 'Anonymous',
                '152.26.69.32': 'Anonymous',
                '152.26.69.33': 'Anonymous',
                '152.26.69.36': 'Anonymous',
                '152.26.69.39': 'Anonymous',
                '152.26.69.40': 'Anonymous',
                '152.26.69.41': 'Anonymous',
                '152.26.69.42': 'Anonymous',
                '152.26.69.45': 'Anonymous',
                '187.18.122.211': 'Transparent',
                '192.99.20.92': 'Anonymous',
                '193.37.152.186': 'Transparent',
                '210.51.48.206': 'Transparent',
                '218.76.76.11': 'Transparent',
                '218.92.227.170': 'Anonymous',  # OLD: 'High' but in headers have Proxy-Connection: close
                '219.92.17.54': 'Transparent',
                '222.243.16.44': 'Transparent',
                '60.191.168.43': 'Transparent',
                '62.204.241.146': 'Transparent',
                '83.241.46.175': 'Transparent',
                '212.119.242.68': 'Transparent',
                '221.214.166.181': 'Transparent',
                '190.15.192.120': 'Transparent',
                '213.184.225.225': 'Transparent',
                }

    proxies = sorted(proxies, key=lambda p: (len(p.host[:p.host.find('.')]), p.host[:3]))
    new = defaultdict(list)
    notFound = defaultdict(list)
    badAnon = []
    _all_good_hosts = []
    for p in proxies:
        _all_good_hosts.append(p.host)
        for pt in p.ptype:
            if pt == 'HTTP':
                aLVL = anon_lvl.get(p.host)
                if aLVL != p.anonymity['HTTP']:
                    badAnon.append('%s: OLD: %s; NOW: %s' % (p.host, aLVL, p.anonymity['HTTP']))
            if p.host in d[pt]:
                continue
            elif p.host not in d[pt]:
                new[pt].append(p)
    for pt, hosts in d.items():
        for host in hosts:
            if host not in _all_good_hosts:
                notFound[pt].append(host)

    print('NEW:::')
    pprint.pprint(new)
    print('\nNOT FOUND:::')
    pprint.pprint(notFound)
    print('\nBAD ANON LVL:::')
    pprint.pprint(badAnon)

    psocks5 = sorted(s.get_good_proxies('SOCKS5'), key=lambda p: (len(p.host[:p.host.find('.')]), p.host[:3]))
    psocks4 = sorted(s.get_good_proxies('SOCKS4'), key=lambda p: (len(p.host[:p.host.find('.')]), p.host[:3]))
    phttps = sorted(s.get_good_proxies('HTTPS'), key=lambda p: (len(p.host[:p.host.find('.')]), p.host[:3]))
    phttp = sorted(s.get_good_proxies('HTTP'), key=lambda p: (len(p.host[:p.host.find('.')]), p.host[:3]))
    print('The amount of good proxies: %d\n' % len(s.get_good_proxies()))
    print('SOCKS5 (count: %d): %s\n' % (len(psocks5), psocks5))
    print('SOCKS4 (count: %d): %s\n' % (len(psocks4), psocks4))
    print('HTTPS (count: %d): %s\n' % (len(phttps), phttps))
    print('HTTP (count: %d): %s\n' % (len(phttp), phttp))

def show_stats(s):
    proxies = s.get_good_proxies()
    errors = Counter()
    stat = {'Connection failed': [],
            'Connection timeout': [],
            'Connection success': []}

    for p in sorted(proxies, key=lambda p: p.host):
        errors.update(p.errors)
        msgs = [l[0] for l in p.log()]

        if 'Connection: success' in ' '.join(msgs):
            print(p)
            stat['Connection success'].append(p)
            events_by_ngtr = defaultdict(list)
            for event, runtime in p.log():
                if 'Host resolved' in event:
                    print('\t{:<70} Runtime: {:.4f}'.format(
                        event.replace('None: ', ''), runtime))
                else:
                    ngtrChars = event.find(':')
                    ngtr = event[:ngtrChars]
                    # event = 'SOCKS5: Connection: success' =>
                    # ngtr = 'SOCKS5'
                    event = event[ngtrChars+2:]
                    events_by_ngtr[ngtr].append((event, runtime))

            for ngtr, events in sorted(events_by_ngtr.items(),
                                       key=lambda item: item[0]):
                print('\t%s' % ngtr)
                for event, runtime in events:
                    if 'Initial connection' in event:
                        continue
                    elif 'Connection:' in event and\
                         'Connection: closed' not in event:
                        print('\t\t{:<66} Runtime: {:.4f}'.format(event, runtime))
                    else:
                        print('\t\t\t{:<62} Runtime: {:.4f}'.format(event, runtime))
        elif 'Connection: failed' in ' '.join(msgs):
            stat['Connection failed'].append(p)
        else:
            stat['Connection timeout'].append(p)
    pprint.pprint(stat)
    print('Errors:', errors)


testProxyList = '''
    119.47.91.113:1080
    41.60.130.36:1080
    82.208.95.64:1080
    202.22.195.197:1080
    201.210.227.21:1080
    187.210.37.36:1080
    219.157.77.102:1080
    c-76-124-41-9.hsd1.pa.comcast.net:53641
    77.242.22.254:8741
    110.169.152.251:1080
    thetru2072.lnk.telstra.net:35067
    66.188.42.61:32282
    62.73.97.139:5224
    cpe-217-30-196-65.enet.vn.ua:5600
    180.250.159.19:1080
    vmi15075.contabo.host:3128
    120.195.199.85:80
    static-a68.ekaterinburg.golden.ru:3128
    sophoswebtest.ucps.k12.nc.us:8080
    sophosweb7.ucps.k12.nc.us:8080
    sophosweb4.ucps.k12.nc.us:8080
    sophosweb3.ucps.k12.nc.us:8080
    sophosweb2.ucps.k12.nc.us:8080
    sophosweb15.ucps.k12.nc.us:8080
    sophosweb12.ucps.k12.nc.us:8080
    sophosweb11.ucps.k12.nc.us:8080
    sophosweb10.ucps.k12.nc.us:8080
    sophosweb1.ucps.k12.nc.us:8080
    sokol-rampuse.core.ttnet.cz:8000
    skombro.rogiken.org:8080
    server192.120.itcsa.net:3128
    120.195.201.165:80
    120.195.195.36:80
    radbr.com.br:3128
    120.195.203.213:80
    ns517810.ip-192-99-20.net:3128
    ns506775.ip-198-100-148.net:3128
    ns376204.ip-5-39-81.eu:3128
    ns302694.ip-94-23-200.eu:3128
    mx2.ftnic.net:3128
    218.92.227.170:18186
    mpe-46-175.mpe.lv:8080
    mdh-17-54.tm.net.my:8080
    120.195.206.63:80
    120.195.205.48:80
    120.195.193.109:80
    mail2.jy-hydraulic.com:8089
    www5072uo.sakura.ne.jp:8080
    li634-239.members.linode.com:8080
    leased-line-225-225.telecom.by:8081
    l37-194-52-83.novotelecom.ru:8080
    ip2-232.kortedala.com:8085
    120.195.207.199:80
    120.195.205.116:80
    120.195.200.30:80
    icm-02.cc.umanitoba.ca:8080
    host136-45-231-152.movistar.com.ni:3128
    host-41-222-57-14.cybernet.co.tz:8081
    193.37.152.186:3128
    190.15.192.120:3128
    187.18.122.211:8080
    202.21.176.108:8080
    69.168.242.44:8080
    69.168.255.85:8080
    60.191.174.13:3128
    61.75.2.124:3128
    118.144.156.2:3128
    60.191.168.43:3128
    54.207.45.19:3333
    54.174.168.237:3128
    222.243.16.44:3128
    221.214.166.181:3128
    218.76.76.11:3128'''

judges = ['http://jmof.org/proxyc/engine.php',
          'http://srv.com.eg/proxyc/engine.php',
          'http://www.pechati-don.ru/proxyc/engine.php',
          'http://fitnesser.ru/proxyc/engine.php',
          'http://kiev-hosting.com/prox33/engine.php',
          'http://ftp.cpdis.ru/engine.php',
          'http://shoppingtut.com/proxyc/engine.php',
          'http://web-sit.ru/prox/engine.php',
          'http://xzzy.info/ca/da/erpg.php',
          'http://xrumer.eu/admin/js/temptxt.php',
          'http://www.urlskit.com/herfer/engine.php',
          'http://plgetae.altervista.org/proxyc/engine.php',
          'http://noclo.com/engine.php',
          'http://www.leotraff.com/pp2p/engine.php',
          'http://sickseo.co.uk/proxyc/engine.php',
          'http://ns2.studio-aa.ru/engine.php',
          'http://pharmtex.com/proxyc/engine.php']
