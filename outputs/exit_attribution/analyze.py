"""Exact closed-trade accounting, not parameter fitting or new strategy replay."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime,timezone,timedelta
import csv,json,math
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent
CASES=[]
for y in (2017,2018,2019,2020):
 base=ROOT/f'outputs/monthly_three_versions_2016_2026/{y}'
 dyn=base if y<=2018 else ROOT/f'outputs/er_dynamic_spot_fallback/{y}'
 CASES.append((y,'SPOT_PRICE_SIMULATION','Nov-Dec' if y==2017 else 'full year',base,dyn))
for y in range(2020,2027):
 if y==2020:b=ROOT/'outputs/er_partial_2020';d=ROOT/'outputs/er_dynamic_compare/2020';window='Feb16-Dec31'
 elif y in (2021,2022,2023):b=ROOT/f'outputs/monthly_three_versions_2016_2026/{y}';d=ROOT/f'outputs/er_dynamic_annual_2019_2026/{y}';window='full year'
 elif y in (2024,2025):b=d=ROOT/f'outputs/binance_perpetual_raw_execution/{y}';window='full year'
 else:b=ROOT/'outputs/er_partial_2026';d=ROOT/'outputs/er_dynamic_compare/2026';window='Jan-Oct'
 CASES.append((y,'BINANCE_USDT_PERPETUAL',window,b,d))


def key(t):return (t.get('signal_close_ms',t['signal_ms']-10000),t['side'],t['entry'])
summary=[];details=[];unmatched=[]
for year,market,window,basepath,dynpath in CASES:
 sums=defaultdict(float);counts=defaultdict(int)
 for asset in ('BTC','ETH'):
  bq=json.loads((basepath/asset/'CONTROL_result.json').read_text());dq=json.loads((dynpath/asset/'DYNAMIC_result.json').read_text())
  assert bq['no_OHLC_fallback'] and dq['no_OHLC_fallback']
  assert bq['stats'].get('fees',0)==0 and dq['stats'].get('fees',0)==0
  sums['base_ending']+=bq['ending_equity'];sums['dynamic_ending']+=dq['ending_equity']
  bm={key(t):t for t in bq['trades']};dm={key(t):t for t in dq['trades']}
  assert len(bm)==len(bq['trades']) and len(dm)==len(dq['trades'])
  counts['base_closed']+=len(bm);counts['dynamic_closed']+=len(dm)
  for k in bm.keys()-dm.keys():
   sums['unmatched_effect']-=bm[k]['net'];unmatched.append(dict(year=year,market=market,asset=asset,profile='CONTROL',trade=bm[k]))
  for k in dm.keys()-bm.keys():
   sums['unmatched_effect']+=dm[k]['net'];unmatched.append(dict(year=year,market=market,asset=asset,profile='DYNAMIC',trade=dm[k]))
  sums['open_end_effect']+=(dq['ending_equity']-500-sum(t['net'] for t in dm.values()))-(bq['ending_equity']-500-sum(t['net'] for t in bm.values()))
  for k in sorted(bm.keys()&dm.keys()):
   b= bm[k];d=dm[k];counts['matched_closed']+=1;side=1 if b['side']=='LONG' else -1
   bqty=b['quantity'];dqty=d['quantity'];entry=b['entry'];assert entry==d['entry']
   stage={1:0.,2:0.};normalized={1:0.,2:0.};fills=d.get('partial_fills',[])
   for fill in fills:
    n=fill['stage'];assert n in (1,2)
    effect=fill['quantity']*side*(fill['execution_price']-d['exit']);stage[n]+=effect
    normalized[n]+=1500*(fill['quantity']/dqty)*side*(fill['execution_price']-d['exit'])/entry
    counts[f'stage{n}_fills']+=1
    if effect< -1e-8:counts[f'stage{n}_sold_before_better_final_exit']+=1;sums[f'stage{n}_gross_foregone']-=effect
    elif effect>1e-8:counts[f'stage{n}_saved_reversal']+=1;sums[f'stage{n}_gross_saved']+=effect
   size=(dqty-bqty)*side*(b['exit']-entry)
   final=dqty*side*(d['exit']-b['exit'])
   actual=d['net']-b['net'];decomp=stage[1]+stage[2]+size+final
   assert abs(actual-decomp)<1e-7,(year,market,asset,'cash decomposition',actual,decomp)
   counts['same_entry_time']+=int(b['opened_us']==d['opened_us'])
   counts['same_final_exit_time']+=int(b['closed_us']==d['closed_us'])
   counts['same_final_exit_price']+=int(b['exit']==d['exit'])
   if b['net']<0:
    counts['baseline_losing_trades']+=1
    if not fills:counts['losing_trades_no_reduction']+=1
   if b['net']>0:counts['baseline_winning_trades']+=1
   if fills:counts['trades_with_reduction']+=1
   sums['stage1_effect']+=stage[1];sums['stage2_effect']+=stage[2];sums['size_feedback_effect']+=size;sums['different_final_exit_effect']+=final
   sums['stage1_equal1500_effect']+=normalized[1];sums['stage2_equal1500_effect']+=normalized[2]
   details.append(dict(year=year,market=market,window=window,asset=asset,side=b['side'],opened_us=b['opened_us'],closed_us=b['closed_us'],entry=entry,baseline_exit=b['exit'],dynamic_final_exit=d['exit'],baseline_quantity=bqty,dynamic_initial_quantity=dqty,baseline_net=b['net'],dynamic_net=d['net'],actual_delta_usdt=actual,stage1_direct_effect_usdt=stage[1],stage2_direct_effect_usdt=stage[2],size_feedback_effect_usdt=size,different_final_exit_effect_usdt=final,stage1_equal1500_usdt=normalized[1],stage2_equal1500_usdt=normalized[2],final_rung=b['rung'],partial_fills=fills))
 actual=sums['dynamic_ending']-sums['base_ending'];explained=sum(sums[x] for x in ('stage1_effect','stage2_effect','size_feedback_effect','different_final_exit_effect','unmatched_effect','open_end_effect'))
 assert abs(actual-explained)<1e-6,(year,market,'annual reconciliation',actual,explained)
 row=dict(year=year,market=market,window=window,base_return_pct=(sums['base_ending']/1000-1)*100,dynamic_return_pct=(sums['dynamic_ending']/1000-1)*100,total_difference_pp=actual/10,
  stage1_direct_pp=sums['stage1_effect']/10,stage2_direct_pp=sums['stage2_effect']/10,size_feedback_pp=sums['size_feedback_effect']/10,other_execution_pp=sums['different_final_exit_effect']/10,unmatched_pp=sums['unmatched_effect']/10,open_end_pp=sums['open_end_effect']/10,
  **{k:v for k,v in counts.items()},**{k:v for k,v in sums.items() if 'gross_' in k or 'equal1500' in k})
 summary.append(row)
for name,rows in [('annual_attribution',summary),('trade_attribution',details),('unmatched_trades',unmatched)]:
 (OUT/f'{name}.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
 fields=list(dict.fromkeys(k for q in rows for k in q))
 with (OUT/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
print(json.dumps(summary,ensure_ascii=False))
