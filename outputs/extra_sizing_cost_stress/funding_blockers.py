"""Read-only first unpriced held settlement; no hypothetical full-year result."""
from pathlib import Path
from decimal import Decimal
import json
import shared as s
import importlib.util
_report_spec=importlib.util.spec_from_file_location('extra_cost_readonly_report',s.OUT/'report.py')
r=importlib.util.module_from_spec(_report_spec);_report_spec.loader.exec_module(r)
assert r.__file__==str(s.OUT/'report.py') and hasattr(r,'PERIODS')
O=s.OUT;h=s.z.h

def main():
 out=[]
 for period in ['2020','2021','2022','2023']:
  for asset in ['BTC','ETH']:
   feed=json.loads((O/'funding_data'/period/asset/'result.json').read_text())
   for cost,ref in [('C2','C1'),('C3','C3_NO_FUNDING'),('C4','C4_NO_FUNDING')]:
    for group in s.GROUPS:
     try:q,_=r.load(period,asset,ref,group,'F_TOUCH','STRICT')
     except FileNotFoundError:continue
     trades=r.rows(q);known_transfer_before=False;block=None
     for e in feed['records']:
      t=int(e['fundingTime'])*1000
      trade=next((x for x in trades if x['opened_us']<t<=(x.get('closed_us')or h.us(q['window'][1])-1)),None)
      if not trade or Decimal(e['fundingRate'])==0:continue
      qty=trade['quantity']-sum(f['quantity']for f in trade.get('partial_fills',[])if f['time_us']<t)
      if qty<=0:continue
      if not e.get('markPrice')or Decimal(e['markPrice'])<=0:
       block=dict(period=period,asset=asset,cost=cost,group=group,status='UNVERIFIED',first_held_unpriced_funding_ms=int(e['fundingTime']),first_block_beijing=h.time_s(t),official_rate=e['fundingRate'],official_mark_price=e.get('markPrice'),held_side=trade['side'],held_quantity=qty,signal_close_ms=trade['signal_close_ms'],source_without_funding_cost=ref,exact_known_prefix=not known_transfer_before,scope='read-only first-block evidence; no full-year funded performance');break
      known_transfer_before=True
     if block:out.append(block)
 s.z.csv_dump(O/'funding_blocking_events.csv',out);print('FUNDING_BLOCKED_CASE_EVIDENCE',len(out))
if __name__=='__main__':main()
