import time
import asyncio

from .judge import Judge
from .utils import log
from .negotiators import *


class ProxyChecker:
    __ngtrs = {'HTTP': HttpNgtr(), 'HTTPS': HttpsNgtr(),
              'SOCKS4': Socks4Ngtr(), 'SOCKS5': Socks5Ngtr()}

    def __init__(self,
                 broker,
                 judges,
                 loop=None):
        self._broker = broker
        self._judges = judges
        self._types = None
        self._countries = None
        self._loop = loop

    async def check_judges(self):
        log.debug('Start check judges')
        stime = time.time()
        await asyncio.gather(*[j.check() for j in self._judges])

        self._judges = [j for j in self._judges if j.isWorking]
        log.info('%d judges added. Runtime: %.4f;' % (
            len(self._judges), time.time()-stime))

        noJudges = []
        disableProtos = []

        if len(Judge.allJudges['HTTP']) == 0:
            noJudges.append('HTTP')
            disableProtos.extend(['HTTP', 'SOCKS4', 'SOCKS5'])
            self._reqHttpProto = False
            # for coroutines, which is already waiting
            Judge.ev['HTTP'].set()
        if len(Judge.allJudges['HTTPS']) == 0:
            noJudges.append('HTTPS')
            disableProtos.append('HTTPS')
            self._reqHttpsProto = False
            # for coroutines, which is already waiting
            Judge.ev['HTTPS'].set()

        [self._ngtrs.pop(proto, None) for proto in disableProtos]

        if noJudges:
            log.warning('Not found judges for the {nojudges} protocol.\n'
                        'Checking proxy on protocols {disp} is disabled.'
                        .format(nojudges=noJudges, disp=disableProtos))
        log.info('Loaded: %d proxy judges' % len(set(self._judges)))

    def set_conditions(self, types={}, countries=None):
        self._reqHttpProto = (not types or '' in types or 'HTTP' in types or
                              'SOCKS4' in types or 'SOCKS5' in types)
        self._reqHttpsProto = (not types or '' in types or 'HTTPS' in types)

        self._types = types
        if not types or (len(types) == 1 and '' in types):
            # for all types and all types with spec anon lvl
            self._ngtrs = self.__ngtrs.copy()
        else:
            self._ngtrs = {name: self.__ngtrs[name]
                          for name, lvls in types.items()}
        self._countries = countries

    def _types_check_passed(self, p):
        if p.isWorking:
            if not self._types:
                return True
            else:
                for name, lvl in p.types.items():
                    needLvls = self._types.get(name)
                    if isinstance(needLvls, str):
                        needLvls = needLvls.split(',')
                    if ((not needLvls) or (lvl and lvl in needLvls)):
                        return True
        p.log('Protocol or the level of anonymity differ from the requested')
        return False

    async def check(self, p):
        if self._reqHttpProto and not Judge.ev['HTTP'].is_set():
            await Judge.ev['HTTP'].wait()

        if self._reqHttpsProto and not Judge.ev['HTTPS'].is_set():
            await Judge.ev['HTTPS'].wait()

        await p.check(self._ngtrs)

        if self._types_check_passed(p):
            self._broker.push_to_result(p)
            log.debug('In results pushed: %s' % p)
