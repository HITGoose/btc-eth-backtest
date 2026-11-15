"""Read completed account ledgers only. No market downloads or account replay."""
from pathlib import Path
import json,csv,numpy as np
O=Path(__file__).resolve().parent

def write(name,rows):
 if not rows:return
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with(O/name).open('w',encoding='utf-8-sig',newline='')as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def key(t):return(t['side'],t['signal_close_ms'])
def metric(v,tr,initial):
 e=np.r_[initial,v]
 return dict(return_pct=100*(v[-1]/initial-1),max_drawdown_pct=100*np.max(1-e/np.maximum.accumulate(e)),closed_trades=len(tr),ending_equity_USDT=float(v[-1]),total_loss_USDT=-sum(min(0,t['net'])for t in tr),max_single_loss_USDT=-min([0.]+[t['net']for t in tr]))
import ast
ns=dict(comparison=[],matches=[])
module=ast.parse((O/'report.py').read_text())
for node in module.body:
 if isinstance(node,ast.FunctionDef)and node.name in ['trade_key','open_key','reason','attribute']:exec(compile(ast.Module(body=[node],type_ignores=[]),str(O/'report.py'),'exec'),ns)
rows=[];direction=[];changes=[]
for year in ['2020','2021','2022']:
 accounts={}
 for asset in ['BTC','ETH']:
  folder=O/'runs/train'/year/asset
  if not(folder/'status.json').exists():continue
  cfg=json.loads((folder/'config.json').read_text());assert cfg['policy']['pause_transition']is True and cfg['V2']is False
  for path in sorted((folder/'results').glob('*_result.json')):
   q=json.loads(path.read_text());name=q['configuration']['source'];tr=q['trades'];v=np.load(path.with_name(path.name.replace('_result.json','_equity.npz')))['marks'];accounts[asset,name]=(q,v)
   rows.append(dict(year=year,asset=asset,candidate=name,**metric(v,tr,500)))
   for side in ['LONG','SHORT']:
    tt=[t for t in tr if t['side']==side]
    direction.append(dict(year=year,asset=asset,candidate=name,side=side,closed_trades=len(tt),wins=sum(t['net']>0 for t in tt),losses=sum(t['net']<0 for t in tt),net_USDT=sum(t['net']for t in tt),total_profit_USDT=sum(max(0,t['net'])for t in tt),total_loss_USDT=-sum(min(0,t['net'])for t in tt)))
  if(asset,'A')not in accounts:continue
  aa={key(t):t for t in accounts[asset,'A'][0]['trades']}
  for a,n in list(accounts):
   if a!=asset or n=='A':continue
   signalsets=json.loads((O/'runs/train'/year/asset/'signals.json').read_text())['accepted'];amap={int(k):v for k,v in signalsets['ZERO_A'].items()};vmap={int(k):v for k,v in signalsets['ZERO_'+n].items()};ns['attribute']('ANNUAL',year,asset,'ZERO',n,accounts[asset,'A'][0],accounts[a,n][0],amap,vmap)
   vv={key(t):t for t in accounts[a,n][0]['trades']};new=[t for k,t in vv.items()if k not in aa];missing=[t for k,t in aa.items()if k not in vv];both=[(t,vv[k])for k,t in aa.items()if k in vv and t['net']<0];short=[t for t in new if t['side']=='SHORT']
   changes.append(dict(year=year,asset=asset,candidate=n,closed_short_change=sum(t['side']=='SHORT'for t in vv.values())-sum(t['side']=='SHORT'for t in aa.values()),new_closed_shorts=len(short),new_closed_shorts_net_USDT=sum(t['net']for t in short),absent_original_wins=sum(t['net']>0 for t in missing),absent_original_profit_USDT=sum(max(0,t['net'])for t in missing),absent_original_losses=sum(t['net']<0 for t in missing),matched_original_losses=len(both),matched_original_losses_worse_count=sum(b['net']<a['net']-1e-8 for a,b in both),matched_original_losses_net_difference_USDT=sum(b['net']-a['net']for a,b in both),matched_original_losses_net_difference_per1000_initial_notional=sum(1000*(b['net']/b['notional']-a['net']/a['notional'])for a,b in both),absent_reason='Requires full signal_attribution.csv: absence alone is not occupancy',account_equity_difference_USDT=accounts[a,n][0]['ending_equity']-accounts[asset,'A'][0]['ending_equity']))
 for n in ['A','B15','B20','B25','C05','C10','C15']:
  if('BTC',n)in accounts and('ETH',n)in accounts:
   b,bv=accounts['BTC',n];e,ev=accounts['ETH',n];assert b['window']==e['window']and len(bv)==len(ev);rows.append(dict(year=year,asset='COMBINED',candidate=n,**metric(bv+ev,b['trades']+e['trades'],1000)))
write('partial_signal_attribution.csv',ns['comparison']);write('partial_trade_matching.csv',ns['matches']);write('partial_training_results.csv',rows);write('partial_direction_summary.csv',direction);write('partial_trade_changes.csv',changes)
for row in rows:
 if row['asset']=='COMBINED':print(json.dumps(row))
