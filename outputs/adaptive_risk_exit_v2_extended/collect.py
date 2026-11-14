from pathlib import Path
import json,csv,numpy as np
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent
rows=[]
for y in (2019,2020,2021,2022,2023,2026):
 row=dict(year=y,period='未验证' if y==2019 else '02-16至12-31' if y==2020 else '01-01至10-31' if y==2026 else '全年')
 if y==2019:row.update(status='UNVERIFIED',reason='无已验证可复用币安永续逐笔输入及充分预热数据')
 else:
  try:
   qs={n:[json.loads((OUT/str(y)/a/f'{n}_result.json').read_text()) for a in ('BTC','ETH')] for n in ('CONTROL','DYNAMIC')}
   for a in ('BTC','ETH'):
    raw=json.loads((OUT/str(y)/a/'raw_sources.json').read_text())
    assert all('/data/futures/um/' in x['url'] and x['official_checksum_match'] for x in raw.values())
    cp=ROOT/(f'outputs/er_partial_2020/{a}_candle_sources.json' if y==2020 else 'outputs/attribution_2026/candle_sources.json' if y==2026 else f'outputs/other_years_050/{y}/{a}_candle_sources.json')
    candles=json.loads(cp.read_text());assert all('/data/futures/um/' in x['url'] and x['official_checksum_match'] for x in candles)
   for n,items in qs.items():
    marks=sum(np.load(OUT/str(y)/a/f'{n}_equity.npy') for a in ('BTC','ETH'));v=np.r_[1000.,marks]
    row[n+'_return_pct']=100*(marks[-1]/1000-1);row[n+'_drawdown_pct']=float(np.max(100*(1-v/np.maximum.accumulate(v))));row[n+'_opens']=sum(q['opens'] for q in items)
   for a,q in zip(('BTC','ETH'),qs['CONTROL']):
    prior_dir=ROOT/('outputs/er_partial_2020' if y==2020 else 'outputs/er_partial_2026' if y==2026 else f'outputs/monthly_three_versions_2016_2026/{y}')
    prior=json.loads((prior_dir/a/'CONTROL_result.json').read_text())
    assert abs(q['ending_equity']-prior['ending_equity'])<1e-7, 'original ER result differs; investigate execution difference'
   for q in qs['DYNAMIC']:
    for t in q['trades']:
     assert len(t['partial_fills'])<=1 and sum(f['quantity'] for f in t['partial_fills'])<=.25*t['quantity']+1e-9
   row['status']='COMPLETE'
  except Exception as ex:row.update(status='UNVERIFIED',reason=repr(ex))
 rows.append(row)
(OUT/'comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
fields=list(dict.fromkeys(k for r in rows for k in r))
with (OUT/'comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
lines=['# V2扩展：币安USDT永续逐笔对照','','V2沿用上一轮同一规则：两闭15m同时MA/MACD弱、余额3%参考预算、每笔最多减一次且≤初始25%，原ER和止损不改。手续费0、滑点0.02%，未计资金费。每年每币初始500，回撤为分钟组合权益。2020/2026不是全年；不以现货补齐。原始ZIP官方SHA256记录各币raw_sources.json。上版固定15USDT预算版未测试这些年份。','','|年份|区间|原ER收益/回撤|V2收益/回撤|','|---|---|---:|---:|']
for r in rows:
 if r['status']=='COMPLETE':lines.append(f"|{r['year']}|{r['period']}|{r['CONTROL_return_pct']:+.2f}% / {r['CONTROL_drawdown_pct']:.2f}%|{r['DYNAMIC_return_pct']:+.2f}% / {r['DYNAMIC_drawdown_pct']:.2f}%|")
 else:lines.append(f"|{r['year']}|{r['period']}|未验证|未验证|")
lines+=['','命令：`/workspace/.venv-btc-eth-original/bin/python -u outputs/adaptive_risk_exit_v2_extended/run.py > outputs/adaptive_risk_exit_v2_extended/run.log 2>&1`；随后运行同目录collect.py。各任务run.log保存实际失败。原代码及原版本不覆盖。限价触达仍为全量成交代理，未模拟深度排队；3%不是最大亏损保证。']
for r in rows:
 if 'reason'in r:lines.append(f"\n{r['year']}未验证原因：{r['reason']}")
(OUT/'report.md').write_text('\n'.join(lines)+'\n');print(json.dumps(rows,ensure_ascii=False))
