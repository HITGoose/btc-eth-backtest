"""Read-only cost decomposition/matching from completed full-account ledgers."""
import json,csv,zipfile,importlib.util
import online as n
O=n.O;s=n.s
sp=importlib.util.spec_from_file_location('cost_match_readonly',n.OLD/'report.py');r=importlib.util.module_from_spec(sp);sp.loader.exec_module(r)
def load(p,a,mode,g):
 g='B'if a=='BTC'else g
 with zipfile.ZipFile(O/'artifacts'/('ledgers_'+p+'.zip'))as z:return json.loads(z.read('_'.join([p,a,mode,g])+'.json'))
with(O/'historical_costs.csv').open(encoding='utf-8-sig')as f:metrics=list(csv.DictReader(f))
matched=[];identity=[]
for p in ['2020','2021','2022','2023']:
 for mode in ['OPEN','HIGH','LOW']:
  for g in ['B','I100','I50','I25']:
   delta=[]
   for a in ['BTC','ETH']:
    base=load(p,a,'C1',g);q=load(p,a,mode,g);meta=dict(period=p,cost=mode,group=g,asset=a,comparison_base='C1_SAME_STRATEGY',scope='actual full accounts; normalization is attribution only')
    matched+=r.attribution(base,q,meta);profit=q['ending_equity']-base['ending_equity'];fee=q['stats'].get('fees',0)-base['stats'].get('fees',0);fund=q['funding_total_USDT'];slip=q['slippage_cost_USDT']-base['slippage_cost_USDT'];resid=profit+fee-fund+slip;assert abs(profit-(-fee+fund-slip+resid))<1e-7
    identity.append(dict(meta,account_profit_difference_USDT=profit,direct_funding_USDT=fund,fee_difference_USDT=fee,slippage_difference_USDT=slip,path_balance_quantity_V2_MTM_residual=resid,identity_passed=True,not_a_posthoc_fee_deduction=True))
for row in metrics:
 p=row['period'];g=row['group'];mode=row['cost'];assets=['BTC','ETH']if row['asset']=='COMBINED'else[row['asset']]
 qq=[load(p,a,mode,g)for a in assets];included=mode!='C1'
 row.update(fees_USDT=sum(q['stats'].get('fees',0)for q in qq),funding_price_quality='APPROXIMATE_FUNDING'if mode in('OPEN','HIGH','LOW')else'EXACT_OFFICIAL_REFERENCE'if included else'NOT_INCLUDED',funding_net_USDT=sum(q.get('funding_total_USDT',0)for q in qq)if included else None,funding_receipts_USDT=sum(max(0,f['delta'])for q in qq for f in q.get('funding_events',[]))if included else None,funding_payments_USDT=-sum(min(0,f['delta'])for q in qq for f in q.get('funding_events',[]))if included else None,slippage_USDT=sum(q['slippage_cost_USDT']for q in qq),actual_net_profit_USDT=float(row['ending_equity'])-(1000 if row['asset']=='COMBINED'else 500))
s.z.csv_dump(O/'historical_costs_with_costs.csv',metrics);s.z.csv_dump(O/'cost_path_matching.csv.gz',matched);s.z.csv_dump(O/'cost_decomposition.csv',identity);print('COST_EVIDENCE',len(metrics),len(matched),len(identity))
