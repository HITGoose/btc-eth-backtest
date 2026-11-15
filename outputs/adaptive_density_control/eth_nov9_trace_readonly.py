"""Read cached bars and existing signals only. No books, orders, price replay or downloads.
Run from repository root with Python3.12; output is indicator evidence, never a new backtest.
"""
from pathlib import Path
import sys,importlib.util,json,inspect,numpy as np
R=Path('/workspace/btc-eth-backtest');O=R/'outputs/adaptive_density_control';sys.path.insert(0,str(O));import signals as g
S=1794175200000;cfg=json.loads((R/'outputs/rebound_annual_zero/recent_config.json').read_text());start=cfg['start_ms']//1000;end=cfg['raw_execution_end_ms']//1000
q=g.make('ETH',R/'outputs/rebound_annual_zero/recent_data',start,end,['A']);leg=q['leg'];raw=q['raw'];i=(S-leg.first)//900000-1;c=raw[:,4];dif=g.r.model.ema(c,12)-g.r.model.ema(c,26);dea=g.r.model.ema(dif,9);reg,levels=g.r.regime.hourly_context(leg.first,c,raw[:,2],raw[:,3],regime_thresholds=g.PAIR)
row=next(x for x in q['diagnostics']['A']if x['signal_close_ms']==S);ma={}
for typ,fn in [('SMA',g.r.model.sma),('EMA',g.r.model.ema)]:
 for n in [20,60,120]:
  x=fn(c,n);ma[f'{typ}{n}']=dict(current=float(x[i]),three_bars_ago=float(x[i-3]),strict_down=bool(x[i]<x[i-3]))
level=levels[(S-900000)//3600000*3600000][-1];edge=float(min(raw[i-32:i,3]));med=float(np.median(raw[i-20:i,5]));sma5=g.r.model.sma(c,5);sma20=g.r.model.sma(c,20)
answer=dict(derivation='Read-only indicator/candidate reconstruction from existing cached15m; no financial replay/download',signal_close_ms=S,bar_open_ms=int(raw[i,0]),OHLCV=raw[i,1:].tolist(),previous_close=float(c[i-1]),previous32_low=edge,previous20_volume_median=med,volume_multiplier=float(raw[i,5]/med),SMA5=float(sma5[i]),SMA20=float(sma20[i]),DIF=float(dif[i]),DEA=float(dea[i]),DIF_minus_DEA=float(dif[i]-dea[i]),six_MA=ma,gate=row,hour_context=list(reg[S//3600000*3600000]),support_level=float(level),A_signal=q['maps']['A'].get(S),warm_first_ms=leg.first,financial_start_ms=cfg['start_ms'],V2_prepare_source=inspect.getsourcefile(g.s.b.p.prepare),V2_prepare_line=inspect.getsourcelines(g.s.b.p.prepare)[1])
a=json.loads((O/'recent/ETH/signals_RAW.json').read_text())['A'];v=json.loads((R/'outputs/rebound_annual_zero/recent/ETH/signals.json').read_text())['core'];a={int(k):x for k,x in a.items()};v={int(k):x for k,x in v.items()if cfg['start_ms']<=int(k)<cfg['raw_execution_end_ms']};answer['cached_signal_comparison']=dict(A_count=len(a),V2_count=len(v),entire_RAW_interval_equal=a==v,A_target=a.get(S),V2_target=v.get(S),differences=[dict(t=k,A=a.get(k),V2=v.get(k))for k in sorted(set(a)|set(v))if a.get(k)!=v.get(k)])
(O/'ETH_NOV9_INDICATORS.json').write_text(json.dumps(answer,indent=2));print(json.dumps(answer,indent=2))
