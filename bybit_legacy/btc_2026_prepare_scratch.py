from pathlib import Path
import pandas as pd
cols = ['timestamp','open','high','low','close']
source = Path('bybit_BTCUSDT_15m_source_scratch.parquet')
if not source.exists():
    raise SystemExit(2)
d = pd.read_parquet(source)
d['timestamp'] = pd.to_datetime(d['date'], utc=True).dt.as_unit('ms').astype('int64')
d = d[cols].set_index('timestamp').sort_index()
old = pd.read_csv('bybit_2025_completed_scratch.csv',usecols=cols).set_index('timestamp').sort_index()
as_ms = lambda t: pd.Timestamp(t).as_unit('ms').value
shared = old.index.intersection(d.index)
prior_year = shared[(shared >= as_ms('2024-12-31T16:00:00Z')) & (shared < as_ms('2025-12-31T16:00:00Z'))]
assert d.index.is_unique and old.index.is_unique
assert len(prior_year) == 35040 and (d.loc[prior_year] == old.loc[prior_year]).to_numpy().all()
start = as_ms('2025-12-31T16:00:00Z')
end = as_ms('2026-09-30T16:00:00Z')
wanted = pd.RangeIndex(start,end,900000)
missing = wanted.difference(d.index)
print('archive last:',pd.Timestamp(d.index[-1],unit='ms',tz='UTC'),'verified 2025:',len(prior_year),'missing Jan-Sep 2026:',len(missing))
if len(missing):
    print(pd.Timestamp(missing[0],unit='ms',tz='UTC'))
    raise SystemExit(3)
prefix = old.loc[(old.index >= start-15*96*900000) & (old.index < start)]
assert len(prefix)==15*96
result = pd.concat([prefix,d.loc[wanted]])
result.to_csv('bybit_BTCUSDT_15m_2026_JanSep_scratch.csv',index_label='timestamp')
