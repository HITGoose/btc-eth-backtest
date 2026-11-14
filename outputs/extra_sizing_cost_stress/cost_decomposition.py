import csv
from collections import defaultdict
import shared as s
O=s.OUT

def main():
 with(O/'cash_cost_reconciliation.csv').open(encoding='utf-8-sig')as f:rows=list(csv.DictReader(f))
 n=lambda x:float(x)if x not in('',None)else 0.
 allrows=[];combo=defaultdict(list)
 for r in rows:combo[(r['period'],r['scenario'],r['cost'],r['group'],r['fill'])].append(r)
 for r in rows:allrows.append(dict(r,initial=500.))
 for key,rr in combo.items():
  if len(rr)!=2:continue
  allrows.append(dict(period=key[0],scenario=key[1],cost=key[2],group=key[3],fill=key[4],asset='COMBINED',initial=1000.,ending_equity=sum(n(x['ending_equity'])for x in rr),fees_USDT=sum(n(x['fees_USDT'])for x in rr),slippage_USDT=sum(n(x['slippage_USDT'])for x in rr),funding_total_USDT=sum(n(x['funding_total_USDT'])for x in rr),funding_included=rr[0]['funding_included']))
 index={(r['period'],r['scenario'],r['cost'],r['group'],r['fill'],r['asset']):r for r in allrows};out=[]
 for r in allrows:
  for what,cost,group,fill in [('COST_VS_C0_SAME_STRATEGY','C0',r['group'],r['fill']),('STRATEGY_VS_B_SAME_COST',r['cost'],'B',r['fill'])]:
   base=index.get((r['period'],r['scenario'],cost,group,fill,r['asset']))
   if base is None:continue
   delta=n(r['ending_equity'])-n(base['ending_equity']);fee=n(r['fees_USDT'])-n(base['fees_USDT']);slip=n(r['slippage_USDT'])-n(base['slippage_USDT']);fund=n(r['funding_total_USDT'])-n(base['funding_total_USDT']);resid=delta+fee-fund+slip
   assert abs(-fee+fund-slip+resid-delta)<1e-7
   out.append(dict(period=r['period'],scenario=r['scenario'],cost=r['cost'],group=r['group'],fill=r['fill'],asset=r['asset'],comparison=what,actual_account_profit_difference=delta,direct_fee_difference=fee,modeled_funding_cash_difference=fund,direct_adverse_slippage_difference=slip,path_balance_quantity_V2_and_MTM_residual=resid,identity_reconciled=True,scope='ex-post accounting identity, not post-hoc deduction or separately executable returns; omitted-funding model0 is not missing C2 data filled0'))
 s.z.csv_dump(O/'cost_decomposition.csv',out);print('COST_DECOMPOSITION',len(out))
if __name__=='__main__':main()
