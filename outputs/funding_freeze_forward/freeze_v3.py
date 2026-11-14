"""Write-once code/config freeze. T0 is strictly after manifest construction."""
import online as n
from pathlib import Path
import json,hashlib,time,os,dataclasses,datetime,sys
O=n.O

def main(commit):
 source=json.loads((O/'source_tree.json').read_text());hashes={}
 for row in source['tree']:
  p=n.R/row['path']
  if row['type']=='blob'and row['path'].endswith('.py')and p.exists():
   raw=p.read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==row['sha'],('locked source mismatch',row['path']);hashes[row['path']]=hashlib.sha256(raw).hexdigest()
 for p in [O/'online.py',O/'live.py',O/'ws_live_v3.py',Path(n.r.selected.FAST_WINDOW_REPORT)]:hashes[str(p.relative_to(n.R))]=hashlib.sha256(p.read_bytes()).hexdigest()
 completed=n.nowus();t0=((completed//1000000+60)//900+1)*900000
 manifest=dict(schema=1,run_id='ws_closed_fix_'+str(t0),base_commit='02608460c21e1f29db7191cffc58fd8f8c0632b4',implementation_commit=commit,created_UTC=n.utc(completed),created_us=completed,T0_ms=t0,T0_UTC=n.utc(t0*1000),T0_Beijing=datetime.datetime.fromtimestamp(t0/1000,datetime.timezone(datetime.timedelta(hours=8))).isoformat(),first_signal_close_ms=t0+900000,code_SHA256=hashes,code_fingerprint=n.digest(hashes),versions=['B','I100','I50','I25'],initial_per_coin_USDT=500,assets=['BTCUSDT','ETHUSDT'],market='BINANCE_USDT_PERPETUAL',source=n.BASE,timezone='UTC stored; reports UTC+8',leverage=3,extra_ratios=dict(I100=1,I50=.5,I25=.25),CORE_and_BTC_ratio=1,fees_per_side_assumed=.0005,exit_adverse_slip=.0002,entry_crosses=False,ENTRY=dataclasses.asdict(n.r.regime.ENTRY),overlay=json.loads(n.r.selected.FAST_WINDOW_REPORT.read_text())['policy'],quantity_step=dict(BTC=.0001,ETH=n.r.model.RULES['ETH'][0]),minimum_notional={a:n.r.model.RULES[a][1]for a in ['BTC','ETH']},price_tick={a:1/n.r.model.SCALES[a]for a in ['BTC','ETH']},poll_seconds=5,poll_phase_seconds=2,order_delay_seconds=10,order_lifetime_ms=n.r.model.ORDER_LIFETIME,CORE_EXTRA='same-direction original .25 complete signal is CORE; only .30 complete is EXTRA; independent signal states; BTC complete same-bar indicator confirmation only for EXTRA',priority='CORE only at original+10; replace EXTRA order or exit EXTRA before submit; never fill CORE on exit event; actual submit clock and60min expiry retained',V2=dict(two_closed_15m=True,budget_rate=.03,max_initial_reduction=.25,once=True,I25_budget_not_scaled=True),fill_proxies=['F_TOUCH','F_THROUGH'],fill_proxy_limitations='full-quantity proxy at limit, no order queue/depth model; F_THROUGH at least one tick beyond limit',funding=dict(mode='EXACT_OFFICIAL_ONLY',economic_time='official integer fundingTime; no8hour grid',missing='halt financial processing, keep collecting; never unknown=0; recovery replay separately labelled',same_time='funding before same-time exchange event in deterministic replay; live availability recorded, no future rate used'),operational=dict(raw_public_REST_poll_seconds=1,closed_Kline_poll_seconds=4,source_stale_halt_seconds=3,clock_skew_max_ms=2000,late_order_dispatch_halt_us=1000000,late_print_before_new_stop='halt and require event-history replay',unclosed_candles_ignored=True,deferred_V2_until_closed_received=True,raw_gap='halt financial path, capture continues',restart='offline portion marked REPLAYED_AFTER_GAP; no silently invented prices'),checkpoints=[dict(day=d,UTC=n.utc(t0*1000+d*86400*1000000),purpose='quality sample count costs risk; not automatic statistical significance')for d in [30,60,90]],no_parameter_selection=True,prior_freeze='FREEZE_WS_V2.json',implementation_fix='Runtime data fix only: native WS raw trades and x=true closed Klines; financial Engine source byte-identical; REST terminal excluded with pagination overlap',raw_stream='wss://fstream.binance.com/stream?streams=btcusdt@trade/ethusdt@trade/btcusdt@kline_15m/ethusdt@kline_15m')
 manifest['operational']['raw_public_REST_poll_seconds']=None
 manifest['operational']['closed_Kline_source']='Official native WebSocket kline_15m x=true only; REST used only for prewarm, terminal rows excluded with overlap'
 manifest['operational']['raw_source']='Official nonaggregated WebSocket @trade; preserve E,T,t,p,q,m,X,st in raw message'
 manifest['operational']['websocket_reconnect']='record gap; halt financial until labelled recovery'
 raw=json.dumps(manifest,ensure_ascii=False,indent=2,default=str).encode();p=O/'FREEZE_WS_V3.json'
 with p.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
 assert n.nowus()<t0*1000
 (O/'FREEZE_WS_V3.sha256').write_text(hashlib.sha256(raw).hexdigest()+'  FREEZE_WS_V3.json\n');p.chmod(0o444);(O/'FREEZE_WS_V3.sha256').chmod(0o444);print(manifest['T0_UTC'],manifest['T0_Beijing'],manifest['code_fingerprint'])
if __name__=='__main__':main(sys.argv[1])
