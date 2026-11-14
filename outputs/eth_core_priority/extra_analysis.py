from pathlib import Path
import csv,json
import strategy as z
OUT=z.OUT
def readcsv(name):
 with(OUT/name).open(encoding='utf-8-sig',newline='')as f:return list(csv.DictReader(f))
def num(x):return float(x)if x not in('',None)else 0.
if __name__=='__main__':
 filters=readcsv('btc_filter_audit.csv');summary=[]
 for cost in z.COSTS:
  for period in['ALL_VERIFIED_D']+z.PERIODS:
   for direction in['ALL','LONG','SHORT']:
    for passed in('True','False'):
     use=[x for x in filters if x['cost']==cost and(period=='ALL_VERIFIED_D'or x['period']==period)and(direction=='ALL'or x['side']==direction)and x['BTC_confirm_pass']==passed]
     ts=[x for x in use if x['D_status']=='CLOSED'];wins=[num(x['D_net'])for x in ts if num(x['D_net'])>0];loss=[-num(x['D_net'])for x in ts if num(x['D_net'])<0]
     summary.append(dict(period=period,cost=cost,direction=direction,BTC_confirm_pass=passed,candidates=len(use),D_unknown=sum(x['D_status']=='NOT_EVALUATED'for x in use),D_closed=len(ts),D_wins=len(wins),D_losses=len(loss),D_winrate_pct=100*len(wins)/len(ts)if ts else None,D_net=sum(wins)-sum(loss),D_profit_factor=sum(wins)/sum(loss)if sum(loss)else None,D_mean_net_per_1000=sum(num(x['D_net_per_1000_initial'])for x in ts)/len(ts)if ts else None,scope='D executed trades only, conditional hindsight attribution; candidate rejection is contemporaneous'))
 z.csv_dump(OUT/'btc_filter_summary.csv',summary)
 attrs=readcsv('trade_attribution.csv');concentration=[]
 for v,b in[('G','D'),('H','D'),('I','D'),('G','B'),('H','B'),('I','B')]:
  for cost in z.COSTS:
   use=[x for x in attrs if x['variant']==v and x['base']==b and x['cost']==cost and x['asset']=='ETH'];positive=sorted([num(x['actual_USDT_delta'])for x in use if num(x['actual_USDT_delta'])>0],reverse=True);total=sum(num(x['actual_USDT_delta'])for x in use)
   concentration.append(dict(variant=v,base=b,cost=cost,periods=','.join(sorted({x['period']for x in use})),actual_delta=total,positive_delta=sum(positive),top1_positive_share=sum(positive[:1])/sum(positive)if positive else None,top5_positive_share=sum(positive[:5])/sum(positive)if positive else None,delta_without_top5_positive_attribution=total-sum(positive[:5]),scope='arithmetic attribution sensitivity, NOT executable rerun with five trades removed'))
 z.csv_dump(OUT/'concentration_overall.csv',concentration);print('EXTRA_ANALYSIS',len(summary),len(concentration))
 c=z.module('priority_extra_collect',OUT/'collect.py');h=z.module('priority_extra_helpers',OUT/'analysis_helpers.py');quality=[]
 for period in z.PERIODS:
  for cost in z.COSTS:
   for group in z.GROUPS:
    try:q,eq=c.load(period,'ETH',cost,group)
    except FileNotFoundError:continue
    for origin in('CORE','EXTRA'):
     for direction in('ALL','LONG','SHORT'):
      use=[t for t in q['trades']if t['origin']==origin and(direction=='ALL'or t['side']==direction)];wins=sum(t['net']>0 for t in use);profit=sum(max(0.,t['net'])for t in use);loss=-sum(min(0.,t['net'])for t in use);norm=[t['net']/(t['entry']*t['quantity'])*1000 for t in use]
      quality.append(dict(period=period,cost=cost,group=group,origin=origin,direction=direction,closed=len(use),wins=wins,losses=sum(t['net']<0 for t in use),win_rate_pct=100*wins/len(use)if use else None,net=profit-loss,gross_profit=profit,gross_loss=loss,profit_factor=profit/loss if loss else None,mean_net_per_1000=sum(norm)/len(norm)if norm else None,max_loss=min([0]+[t['net']for t in use]),scope='actual full account closed trades classified at signal time; per1000 is attribution not rerun'))
 z.csv_dump(OUT/'signal_quality.csv',quality);print('QUALITY',len(quality),'rows')
 amplified=[]
 for x in attrs:
  if x['old_status']!='CLOSED'or x['new_status']!='CLOSED'or num(x['old_net'])>=0:continue
  actual=num(x['new_net'])<num(x['old_net'])-1e-8;norm=num(x['new_normalized_1000'])<num(x['old_normalized_1000'])-1e-8
  if not(actual or norm):continue
  samefinal=all(x['old_'+f]==x['new_'+f]for f in('opened_us','closed_us','entry','exit'))
  partial=lambda name:[(p['time_us'],p['execution_price'])for p in json.loads(x[name]or'[]')]
  samepartials=partial('old_partial_fills')==partial('new_partial_fills')
  amplified.append(dict(x,loss_worsened_actual=actual,loss_worsened_normalized=norm,same_entry_exit_prices_and_times=samefinal,same_partial_prices_and_times=samepartials,classification='SIZING_OR_PARTIAL_FRACTION_ONLY'if samefinal and samepartials else'V2_PARTIAL_PATH_OR_ROUNDING'if samefinal else'ENTRY_EXIT_PATH_ALSO_CHANGED'))
 z.csv_dump(OUT/'loss_amplification.csv',amplified);print('LOSS_AMPLIFICATION',len(amplified))
 extra_concentration=[]
 for group in('G','H','I'):
  for cost in z.COSTS:
   use=[x for x in attrs if x['variant']==group and x['base']=='B'and x['cost']==cost and x['asset']=='ETH'and x['new_status']=='CLOSED'and x['new_origin']=='EXTRA'];wins=sorted([num(x['new_net'])for x in use if num(x['new_net'])>0],reverse=True)
   extra_concentration.append(dict(group=group,cost=cost,EXTRA_closed=len(use),EXTRA_winners=len(wins),EXTRA_gross_profit=sum(wins),top1_profit_share=sum(wins[:1])/sum(wins)if wins else None,top5_profit_share=sum(wins[:5])/sum(wins)if wins else None,scope='actual EXTRA closed trades; no selected-case rule or rerun'))
 z.csv_dump(OUT/'extra_profit_concentration.csv',extra_concentration)
