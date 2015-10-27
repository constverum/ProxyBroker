import pickle
import pprint
import os.path
from collections import defaultdict, Counter


def test(s, show=False):
    try:
        with open(resultsPath, 'rb') as f:
            lastResults = pickle.load(f)
            # print('lastResults UN-PICKLED:::')
            # pprint.pprint(lastResults)
            # print('lastResults 0:', lastResults['104.131.209.138'].host, lastResults['104.131.209.138'].types, lastResults['104.131.209.138'].anonymity)
            # print('lastResults 0:', lastResults['104.131.209.138'])
    except (FileNotFoundError, EOFError):
        lastResults = {}
        # print('lastResults::: %r' % lastResults)

    proxies = s.get_good_proxies()
    # proxies = sorted(proxies, key=lambda p: (len(p.host[:p.host.find('.')]), p.host[:3]))
    new = defaultdict(list)
    notFound = defaultdict(list)
    badAnonLvl = []
    all_good_hosts = []
    for p in proxies:
        all_good_hosts.append(p.host)
        for pt in p.types:
            oldProxyObj = lastResults.get(p.host)
            if oldProxyObj:
                anonLvl = oldProxyObj.types.get(pt)
                if anonLvl != p.types[pt]:
                    badAnonLvl.append('%s: OLD: %s; NOW: %s' % (p.host, anonLvl, p.types[pt]))
            elif not oldProxyObj:
                new[pt].append(p)
    for p in lastResults.values():
        for pt in p.types:
            if p.host not in all_good_hosts:
                notFound[pt].append(p.host)

    lmb = lambda p: (len(p.host[:p.host.find('.')]), p.host[:3])
    s5 = sorted(s.get_good_proxies('SOCKS5'), key=lmb)
    s4 = sorted(s.get_good_proxies('SOCKS4'), key=lmb)
    c = sorted(s.get_good_proxies('CONNECT'), key=lmb)
    hs = sorted(s.get_good_proxies('HTTPS'), key=lmb)
    h = sorted(s.get_good_proxies('HTTP'), key=lmb)
    print('The amount of good proxies: {all}\n'
          'SOCKS5 (count: {ls5}): {s5}\nSOCKS4 (count: {ls4}): {s4}\n'
          'CONNECT (count: {lc}): {c}\nHTTPS (count: {lhs}): {hs}\n'
          'HTTP (count: {lh}): {h}\n'.format(
            all=len(proxies), s5=s5, ls5=len(s5), s4=s4, ls4=len(s4),
            c=c, lc=len(c), hs=hs, lhs=len(hs), h=h, lh=len(h)))

    with open(resultsPath, 'wb') as f:
        data = {p.host: p for p in proxies}
        pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
        # print('PICKLED:::')
        # pprint.pprint(data)

    if show:
        print('NEW:::')
        pprint.pprint(new)
        print('\nNOT FOUND:::')
        pprint.pprint(notFound)
        print('\nBAD ANON LVL:::')
        pprint.pprint(badAnonLvl)

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


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
resultsPath = BASE_DIR+'/data/results.dat'

proxyListPath = BASE_DIR+'/data/proxy_list.txt'
with open(proxyListPath, 'r') as f:
    proxies = [p.lstrip().split(':') for p in f.readlines()
                                     if p and not p.startswith('#')]

judgeListPath = BASE_DIR+'/data/judge_list.txt'
with open(judgeListPath, 'r') as f:
    judges = [p for p in f.readlines() if p and not p.startswith('#')]



