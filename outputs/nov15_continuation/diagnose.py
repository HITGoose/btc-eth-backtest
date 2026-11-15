from pathlib import Path
import sys,json,datetime
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'outputs/extra_sizing_cost_stress'));import funded_replay as w
s=w.s;z=w.z;np=w.np;TZ=datetime.timezone(datetime.timedelta(hours=8));FROM=int(datetime.datetime(2026,11,9,tzinfo=TZ).timestamp()*1000);END=json.loads((O/'data_manifest.json').read_text())['signal_end_ms'];CUT=1794614400000

def local(ms):return datetime.datetime.fromtimestamp(ms/1000,TZ).isoformat()
def occupied(q,t):
 for x in q['trades']:
  if x['opened_us']<=t*1000<(x['closed_us']or CUT*1000):return 'POSITION'
 pos=q['state_at_end']['position']
 if pos and q['state_at_end']['position_opened_us']<=t*1000:return 'POSITION'
 events=[e for e in q['events'] if e['time_us']<=t*1000 and e['event'] in ['order_sent','limit_touch_proxy_fill','order_expired','priority_cancel_extra_order']]
 if events and events[-1]['event']=='order_sent' and t*1000<events[-1]['time_us']+3600000000:return 'PENDING_ORDER'
 return 'IDLE'
allrows=[];trades=[];summary=[];missed=[]
for asset in ['BTC','ETH']:
 old=z.prepare('NOV',asset);leg,_,_,_,policy,pair=w.b.p.prepare(asset,O/'data'/f'{asset}_15m.csv',old['start'],END//1000)
 _,core,_,_,_=z.s.prepare(asset,O/'data',old['start'],END//1000,.25,leg,policy,pair);_,wide,_,_,_=z.s.prepare(asset,O/'data',old['start'],END//1000,.30,leg,policy,pair)
 # Separate, read-only complete direction probe, even when bottom-level candidate absent.
 _,ctx=z.s.clone_schedule(.25)(asset,z.s.Probe(leg,-1),price_file=O/'data'/f'{asset}_15m.csv',include_gate_confirmation=True,regime_thresholds=pair,use_entry_crosses=False)
 raw=np.loadtxt(O/'data'/f'{asset}_15m.csv',delimiter=',',skiprows=1);raw=raw[(raw[:,0]>=leg.first)&(raw[:,0]<leg.end)]
 for group in(['B']if asset=='BTC'else ['B','I100','I50','I25']):
  q=json.loads((O/'runs'/asset/'results'/f'C2_{group}_F_TOUCH_result.json').read_text());maps=json.loads((O/'runs'/asset/'signals.json').read_text())['accepted'][f'C2_{group}_F_TOUCH'];oldsignals={int(t):v for t,v in maps.items()};btc_full=core
  if asset=='ETH':
   bl,_,_,_,bp,br=w.b.p.prepare('BTC',O/'data/BTC_15m.csv',old['start'],END//1000);btc_full=z.s.prepare('BTC',O/'data',old['start'],END//1000,.25,bl,bp,br)[1]
  signals=core if asset=='BTC'or group=='B'else z.classify(core,wide,btc_full,'I')[0]
  assert {t:v for t,v in signals.items()if t<CUT}==oldsignals
  sent={int(e.get('signal_close_ms',e['time_us']//1000-10000)):e for e in q['events']if e['event']=='order_sent'};filled={t['signal_close_ms']:t for t in q['trades']}
  if asset=='BTC':assert all(t['origin']=='CORE'for t in q['trades'])
  for t,c in ctx.items():
   if t<FROM:continue
   i=(t-leg.first)//900000-1;gate=c['gate_confirmation'];failed=[];threshold=.25 if group=='B'or asset=='BTC'else .30
   if leg.squeeze[96][i]>threshold:failed.append('HISTORICAL_DENSITY')
   if leg.down[i]<6:failed.append('SIX_MA_NOT_ALL_DOWN')
   if not leg.below_band[i]:failed.append('CLOSE_NOT_BELOW_SIX')
   if leg.histogram[i]>=0:failed.append('MACD_NOT_SHORT')
   if c['regime']=='transition':failed.append('ER_TRANSITION')
   elif c['regime']=='range':
    if leg.width[i]>.5:failed.append('RANGE_WIDTH')
   elif c['regime']!='down':failed.append('ER_NOT_DOWN')
   else:
    if not gate['short_term_alignment']:failed.append('SMA5_20')
    if not ((gate['distance_to_confirmed_hourly_level_pct'] is not None and gate['distance_to_confirmed_hourly_level_pct']<=2) or gate['directional_volume_breakout'] or gate['confirmed_retest']):failed.append('TREND_LEVEL_VOLUME_RETEST')
   if asset=='ETH'and group!='B'and wide.get(t)==-1 and core.get(t)!=-1 and btc_full.get(t)!=-1:failed.append('BTC_SAME_BAR_CONFIRM')
   eligible=signals.get(t)==-1
   if t>=CUT:status='UNVERIFIED_EXECUTION_MISSING_RAW';occ='UNVERIFIED'
   else:
    occ=occupied(q,t+10000)
    if t in filled:status='FILLED'
    elif t in sent:status='PENDING_OR_EXPIRED_UNFILLED'
    elif not eligible:status='NO_REENTRY_SIGNAL'
    elif occ!='IDLE':status='BLOCKED_'+occ
    else:status='NOT_EVALUATED'
   row=dict(asset=asset,group=group,signal_close_ms=t,Beijing=local(t),close=float(raw[i,4]),eligible_short=eligible,historical_minimum_bandwidth_pct=float(leg.squeeze[96][i]),current_bandwidth_pct=float(leg.width[i]),down_lines=int(leg.down[i]),close_below_six=bool(leg.below_band[i]),macd=float(leg.histogram[i]),ER=c['regime'],gate_confirmation=json.dumps(gate,ensure_ascii=False),failed_conditions=';'.join(failed),execution=status,occupancy_at_submit=occ)
   allrows.append(row)
  for tr in q['trades']:
   if tr['closed_us']>=FROM*1000:trades.append(dict(asset=asset,group=group,**tr,signal_Beijing=local(tr['signal_close_ms']),opened_Beijing=local(tr['opened_us']/1000),closed_Beijing=local(tr['closed_us']/1000)))
  eq=np.load(O/'runs'/asset/'results'/f'C2_{group}_F_TOUCH_equity.npz')['marks'];ix=(FROM//1000-old['start'])//60;equity9=float(eq[ix-1]);summary.append(dict(asset=asset,group=group,Nov9_start_equity=equity9,ending_equity=q['ending_equity'],Nov9_to_verified_net=q['ending_equity']-equity9,Nov9_return_pct=100*(q['ending_equity']/equity9-1),Nov1_return_pct=100*(q['ending_equity']/500-1),through_Beijing=local(CUT),state_at_end=q['state_at_end']))
  # Each completed short's post-exit decline until next short fill or verified end; descriptive windows, not causal missed profits.
  short=[t for t in q['trades']if t['side']=='SHORT'];pricebars=raw
  for n,tr in enumerate(short):
   if tr['closed_us']<FROM*1000:continue
   lo=tr['closed_us']//1000;hi=short[n+1]['opened_us']//1000 if n+1<len(short)else CUT;bars=pricebars[(pricebars[:,0]>=lo)&(pricebars[:,0]+900000<=hi)]
   if not len(bars):continue
   low=float(bars[:,3].min());rows=[x for x in allrows if x['asset']==asset and x['group']==group and lo<=x['signal_close_ms']<hi];unfilled=sum(x['execution']=='PENDING_OR_EXPIRED_UNFILLED'for x in rows)
   missed.append(dict(asset=asset,group=group,exit_Beijing=local(lo),exit_price=tr['exit'],exit_reason=tr['reason'],window_end_Beijing=local(hi),post_exit_minimum_completed15m_low=low,subsequent_decline_pct=max(0,100*(tr['exit']-low)/tr['exit']),short_signal_count=sum(x['eligible_short']for x in rows),unfilled_signals=unfilled,cause='EXIT_THEN_NO_REENTRY_SIGNAL'if not any(x['eligible_short']for x in rows)else'EXIT_WITH_UNFILLED_ORDERS'if unfilled else'EXIT_THEN_REENTRY_OR_OCCUPANCY',not_counterfactual_profit=True))
z.csv_dump(O/'short_conditions_15m.csv',allrows);z.csv_dump(O/'trades_since_Nov9.csv',trades);s.dump(O/'account_summary.json',summary);z.csv_dump(O/'post_exit_declines.csv',missed);print('DIAGNOSED',len(allrows),len(trades),len(missed))
