from pathlib import Path
import json,csv
import strategy as z
OUT=z.OUT
if __name__=='__main__':
 a=json.loads((OUT/'analysis.json').read_text());assert {x['period']for x in a['availability']}==set(z.PERIODS),'Wait for all-period analysis'
 m={(x['period'],x['cost'],x['group'],x['asset'],x['direction']):x for x in a['metrics']};summary=[]
 for v,b in[('G','D'),('H','D'),('I','D'),('G','B'),('H','B'),('I','B')]:
  for cost in z.COSTS:
   use=[x for x in a['impact']if x['variant']==v and x['base']==b and x['cost']==cost and x['asset']=='ETH'and x['direction']=='ALL'];periods=[x['period']for x in use];improve=[];worse_dd=[];worse_month=[];worse_tail=[];worse_normtail=[]
   for period in periods:
    old=m[period,cost,b,'COMBINED','ALL'];new=m[period,cost,v,'COMBINED','ALL']
    if new['return_pct']>old['return_pct']+1e-8:improve.append(period)
    if new['max_drawdown_pct']>old['max_drawdown_pct']+1e-8:worse_dd.append(period)
    if new['worst_month_return_pct']<old['worst_month_return_pct']-1e-8:worse_month.append(period)
    old=m[period,cost,b,'ETH','ALL'];new=m[period,cost,v,'ETH','ALL']
    if new['max_single_trade_loss']<old['max_single_trade_loss']-1e-8:worse_tail.append(period)
    if new['max_loss_per_1000_initial_notional']<old['max_loss_per_1000_initial_notional']-1e-8:worse_normtail.append(period)
   summary.append(dict(variant=v,base=b,cost=cost,periods=periods,actual_USDT_delta=sum(x['actual_USDT_delta']for x in use),normalized_1000_delta=sum(x['normalized_1000_delta']for x in use),gross_loss_delta=sum(x['gross_loss_delta']for x in use),fees_delta=sum(x['fees_delta']for x in use),lost_B_or_D_winners=sum(x['lost_winners']for x in use),lost_B_or_D_profit=sum(x['lost_winner_profit']for x in use),old_losses_worsened_actual=sum(x['old_losing_worsened_actual']for x in use),old_losses_worsened_normalized=sum(x['old_losing_worsened_normalized']for x in use),return_improved=improve,DD_worsened=worse_dd,worst_month_worsened=worse_month,tail_USDT_worsened=worse_tail,tail_per1000_worsened=worse_normtail))
 z.dump(OUT/'summary_stats.json',summary)
 print(json.dumps(summary,ensure_ascii=False,indent=2))
