from pathlib import Path
import json,numpy as np,csv
from datetime import datetime,timezone,timedelta
ROOT=Path('/workspace/btc-eth-backtest');OUT=Path(__file__).resolve().parent;summary=[];details=[]
def key(t):return (t['signal_close_ms'],t['side'],t['entry'])
for y in (2024,2025):
 totals=dict(direct=0.,sizing=0.,execution=0.,end_open=0.,actual=0.,gross_foregone=0.,gross_saved=0.)
 stats=dict(matched=0,same_open=0,same_exit=0,same_exit_price=0,partial_fills=0,reduced_trades=0,repeated_reduction_trades=0,winner_reduced=0,loser_reduced=0,sales_before_better_final=0,sales_saved_reversal=0)
 fractions=[];first_cuts=[];winner_fraction=[];half_or_more=0
 for a in ('BTC','ETH'):
  folder=ROOT/f'outputs/adaptive_risk_exit/{y}/{a}'
  bq=json.loads((folder/'CONTROL_result.json').read_text());dq=json.loads((folder/'DYNAMIC_result.json').read_text());bm={key(t):t for t in bq['trades']};dm={key(t):t for t in dq['trades']};assert bm.keys()==dm.keys()
  totals['actual']+=dq['ending_equity']-bq['ending_equity'];totals['end_open']+=(dq['ending_equity']-500-sum(t['net'] for t in dm.values()))-(bq['ending_equity']-500-sum(t['net'] for t in bm.values()))
  for k,b in bm.items():
   d=dm[k];side=1 if b['side']=='LONG' else -1;fills=d['partial_fills'];initial=d['quantity'];cut=sum(f['quantity'] for f in fills)/initial
   direct=sum(f['quantity']*side*(f['execution_price']-d['exit']) for f in fills);size=(initial-b['quantity'])*side*(b['exit']-b['entry']);execution=initial*side*(d['exit']-b['exit']);assert abs((d['net']-b['net'])-(direct+size+execution))<1e-7
   totals['direct']+=direct;totals['sizing']+=size;totals['execution']+=execution
   stats['matched']+=1;stats['same_open']+=b['opened_us']==d['opened_us'];stats['same_exit']+=b['closed_us']==d['closed_us'];stats['same_exit_price']+=b['exit']==d['exit'];stats['partial_fills']+=len(fills)
   if fills:
    stats['reduced_trades']+=1;stats['repeated_reduction_trades']+=len(fills)>1;fractions.append(cut);first_cuts.append(fills[0]['quantity']/initial);half_or_more+=cut>=.5
    if b['net']>0:stats['winner_reduced']+=1;winner_fraction.append(cut)
    if b['net']<0:stats['loser_reduced']+=1
   for f in fills:
    effect=f['quantity']*side*(f['execution_price']-d['exit'])
    if effect< -1e-8:stats['sales_before_better_final']+=1;totals['gross_foregone']-=effect
    elif effect>1e-8:stats['sales_saved_reversal']+=1;totals['gross_saved']+=effect
   detail=dict(year=y,asset=a,side=b['side'],opened_us=b['opened_us'],closed_us=b['closed_us'],entry=b['entry'],exit=b['exit'],base_net=b['net'],adaptive_net=d['net'],opening_cash=d['opening_sleeve_cash_usdt'],reduced_fraction=cut,first_cut_fraction=fills[0]['quantity']/initial if fills else 0,number_reductions=len(fills),direct_effect=direct,sizing_effect=size,execution_effect=execution,final_price_gain_pct=side*(b['exit']/b['entry']-1)*100,partial_fills=fills)
   details.append(detail)
 assert abs(totals['actual']-totals['direct']-totals['sizing']-totals['execution']-totals['end_open'])<1e-6
 summary.append(dict(year=y,**{k:v/10 for k,v in totals.items()},**stats,median_first_cut_pct=float(np.median(first_cuts)*100),median_total_cut_pct=float(np.median(fractions)*100),mean_total_cut_pct=float(np.mean(fractions)*100),median_winner_total_cut_pct=float(np.median(winner_fraction)*100),trades_cut_at_least_half=half_or_more))
for name,rows in [('summary',summary),('trades',details)]:
 (OUT/f'{name}.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
 with (OUT/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(summary,ensure_ascii=False))
for y in (2024,2025):
 rr=sorted([r for r in details if r['year']==y],key=lambda r:r['direct_effect'])
 print('EXAMPLES',y,json.dumps([{k:v for k,v in r.items() if k!='partial_fills'} for r in rr[:3]],ensure_ascii=False))
