from pathlib import Path
from types import SimpleNamespace
import strategy as z
m=z.module('priority_archive_reference_tests',z.OUT/'replay.py')
w=SimpleNamespace(prior=lambda *args:(Path('/tmp/ABSENT_REFERENCE_LEDGER.json'),Path('/tmp/ABSENT_REFERENCE_EQUITY.npy')))
checks=[]
for period in z.PERIODS:
 for asset in('BTC','ETH'):
  for cost in z.COSTS:
   for group in(['B']if asset=='BTC'else['B','D']):
    q,source,npref=m.expected(period,asset,cost,group,w)
    if period=='2025'and asset=='ETH'and group=='D':assert q is None;continue
    assert q is not None and not npref and source['archive'];assert q['asset']==asset
    checks.append(dict(period=period,asset=asset,cost=cost,group=group,archived_JSON_reference_found=True,minute_reference_not_invented=True))
z.dump(z.OUT/'archive_reference_tests.json',dict(passed=True,total=len(checks),checks=checks));print('PASS',len(checks),'archived ledger reference lookups')
