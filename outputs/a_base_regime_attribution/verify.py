from pathlib import Path
import csv,json,hashlib
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent
read=lambda n:list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
rows=read('trade_details.csv');ss=read('state_summary.csv');rec=read('account_reconciliation.csv');assert len(rec)==28 and len(rows)==1800
for x in rec:
 p=R/'outputs/a_exit_regime_sizing/runs'/x['year']/x['asset']/(x['fee_scenario']+'_A_BASE_result.json');assert hashlib.sha256(p.read_bytes()).hexdigest()==x['ledger_SHA256']
for anchor in ['SIGNAL_CLOSE','FILL']:
 for fee in ['ZERO','MAKER_002_SIDE']:
  a=[r for r in ss if r['asset']=='COMBINED'and r['label_anchor']==anchor and r['fee_scenario']==fee];q=[r for r in rec if r['fee_scenario']==fee];assert sum(int(r['closed_count'])for r in a)==895 and sum(int(r['open_count'])for r in a)==5;assert abs(sum(float(r['total_account_contribution_USDT'])for r in a)-sum(float(r['account_net_USDT'])for r in q))<1e-7
  for r in a:
   source=[x for x in rows if x['fee_scenario']==fee and x['signal_state'if anchor=='SIGNAL_CLOSE'else'fill_state']==r['state']and x['record_type']=='CLOSED']
   if source:assert abs(sum(float(x['r1000_net'])for x in source)/len(source)-float(r['closed_r1000_mean']))<1e-10
result=dict(passed=True,unchanged_source_ledgers=28,closed_per_fee=895,open_per_fee=5,all_anchors_independently_reconciled=True,normalized_means_are_per_trade_arithmetic=True,max_account_residual_USDT=max(abs(float(x['residual_USDT']))for x in rec));(O/'VERIFY.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
