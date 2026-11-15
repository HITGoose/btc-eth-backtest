from pathlib import Path
import json,csv,urllib.request,urllib.parse,hashlib,datetime,concurrent.futures
import numpy as np
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;D=O/'data';D.mkdir(exist_ok=True);C=R/'outputs/nov15_continuation';M=R/'outputs/binance_15m_nov9_15';manifest=json.loads((M/'manifest.json').read_text());END=manifest['end_exclusive_ms']
for asset in ['BTC','ETH']:
 old=np.loadtxt(C/'data'/f'{asset}_15m.csv',delimiter=',',skiprows=1);rows=list(csv.DictReader((M/f'{asset}USDT_15m_20261109_20261115.csv').open(encoding='utf-8-sig')));recent=np.array([[float(r[k])for k in ['open_time_ms','open','high','low','close','volume_base']]for r in rows]);ix={int(r[0]):r for r in recent};overlap=[r for r in old if int(r[0])in ix];assert all(np.allclose(r,ix[int(r[0])],rtol=1e-12,atol=1e-7)for r in overlap);combined=np.r_[old,recent[recent[:,0]>old[-1,0]]];assert np.array_equal(combined[:,0],np.arange(combined[0,0],END,900000));np.savetxt(D/f'{asset}_15m.csv',combined,header='timestamp,open,high,low,close,volume',comments='',delimiter=',',fmt='%.17g')
 url='https://www.binance.com/fapi/v1/fundingRate?'+urllib.parse.urlencode(dict(symbol=asset+'USDT',startTime=1794614400000,endTime=END-1,limit=1000))
 with urllib.request.urlopen(url,timeout=30)as f:raw=f.read()
 (D/f'{asset}_funding_response.json').write_bytes(raw);new=json.loads(raw);feed=json.loads((C/'data'/f'{asset}_funding.json').read_text())['events'];by={r['time_ms']:r for r in feed}
 for r in new:
  t=int(r['fundingTime']);assert r['symbol']==asset+'USDT'and float(r['markPrice'])>0
  if t in by:assert float(r['fundingRate'])==by[t]['rate']and float(r['markPrice'])==by[t]['mark_price']
  else:by[t]=dict(time_ms=t,rate=float(r['fundingRate']),mark_price=float(r['markPrice']),complete=True,source='BINANCE_USDT_PERPETUAL_OFFICIAL',official_record=r)
 (D/f'{asset}_funding.json').write_text(json.dumps(dict(events=[by[t]for t in sorted(by)],source_url=url,response_SHA256=hashlib.sha256(raw).hexdigest(),received_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2))
(O/'config.json').write_text(json.dumps(dict(start_continuation_ms=1794614400000,end_ms=END,original_account_start_ms=1793462400000,fee_side=.0005,exit_slippage=.0002,poll_seconds=5,poll_phase=2,paths=['OPEN_HIGH_LOW_CLOSE','OPEN_LOW_HIGH_CLOSE'],synthetic_extrema_offsets_seconds=[0,300,600,899],synthetic_print_spacing_seconds=1,note='15m OHLC synthetic path sensitivity, not observed ticks or strict profit bounds; original observed prefix retained; original financial engine unchanged; 15m signals closed only.'),indent=2));print('PREPARED',END)
