from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,csv
P=Path(__file__).resolve().parent;TZ=timezone(timedelta(hours=8));BEGIN=int(datetime(2026,11,9,tzinfo=TZ).timestamp()*1e6);END=int(datetime(2026,11,13,tzinfo=timezone.utc).timestamp()*1e6)
def fmt(us):return datetime.fromtimestamp(us/1e6,TZ).strftime('%m-%d %H:%M:%S.%f')[:-3] if us else '未平仓'
rows=[];allrows={};summaries=[];pairs=[];overlaps=[]
for version,name in [('CONTROL','原ER'),('DYNAMIC','修正版V2')]:
 books={}
 for asset in ('BTC','ETH'):
  q=json.loads((P/'2026'/asset/f'{version}_result.json').read_text());assert q['no_OHLC_fallback']
  trades=[]
  for t in q['trades']:
   trades.append(dict(version=name,asset=asset,signal_us=t['signal_close_ms']*1000,opened_us=t['opened_us'],closed_us=t['closed_us'],side=t['side'],entry=t['entry'],quantity=t['quantity'],exit=t['exit'],realized=t['net'],unrealized=0.,net=t['net'],rung=t['rung'],partial_count=len(t.get('partial_fills',[])),status='已平仓'))
  state=q['state_at_end'];pos=state['position']
  if pos:
   opened=state['position_opened_us'];event=next(e for e in q['events'] if e['event']=='limit_touch_proxy_fill' and e['time_us']==opened);fills=[e for e in q['events'] if e['event']=='partial_exit' and e['time_us']>=opened];realized=sum(e['net_usdt'] for e in fills);unrealized=pos['order']['side']*(q['actual_raw_last_mark']-pos['order']['price'])*pos['order']['qty']
   trades.append(dict(version=name,asset=asset,signal_us=(pos['order']['time']-10000)*1000,opened_us=opened,closed_us=None,side='LONG' if pos['order']['side']==1 else 'SHORT',entry=pos['order']['price'],quantity=event['quantity'],exit=None,realized=realized,unrealized=unrealized,net=realized+unrealized,rung=pos['rung'],partial_count=len(fills),status='持仓，按截止价估值'))
  books[asset]=trades
  chosen=[t for t in trades if BEGIN<=t['opened_us']<END]
  for t in chosen:
   t.update(signal_beijing=fmt(t['signal_us']),opened_beijing=fmt(t['opened_us']),closed_beijing=fmt(t['closed_us']));rows.append(t)
  summaries.append(dict(version=name,asset=asset,opens=len(chosen),realized=sum(t['realized'] for t in chosen),unrealized=sum(t['unrealized'] for t in chosen),net=sum(t['net'] for t in chosen),note='筛选本期开仓交易盈亏；不等于期间账户收益率'))
 for b in books['BTC']:
  for e in books['ETH']:
   if BEGIN<=b['opened_us']<END and BEGIN<=e['opened_us']<END and b['signal_us']==e['signal_us']:
    pairs.append(dict(version=name,signal_beijing=fmt(b['signal_us']),BTC_open=fmt(b['opened_us']),ETH_open=fmt(e['opened_us']),BTC_side=b['side'],ETH_side=e['side'],BTC_net=b['net'],ETH_net=e['net'],combined_net=b['net']+e['net']))
   start=max(b['opened_us'],e['opened_us'],BEGIN);end=min(b['closed_us'] or END,e['closed_us'] or END,END)
   if start<end:overlaps.append(dict(version=name,start_beijing=fmt(start),end_beijing=fmt(end),BTC_side=b['side'],ETH_side=e['side'],BTC_open=fmt(b['opened_us']),ETH_open=fmt(e['opened_us'])))
for filename,records in [('trades.csv',rows),('summary.csv',summaries),('same_signal_pairs.csv',pairs),('overlapping_positions.csv',overlaps)]:
 fields=list(dict.fromkeys(k for r in records for k in r)) or ['none']
 with (P/filename).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)
out=dict(period_beijing=['2026-11-09 00:00:00','2026-11-13 08:00:00 exclusive'],today_after_cutoff='UNVERIFIED: fapi451, archivesNov13/14 404',initialization='Nov1 each asset500 independently per version, no annual carry',summary=summaries,same_signal_pairs=pairs,overlapping_positions=overlaps,trades=rows)
(P/'result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
