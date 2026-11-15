"""Predeclared data-quality observation end, independent of returns or trade results."""
from pathlib import Path
import json,time,pickle
import online as n
O=n.O;m=json.loads((O/'FREEZE_WS_V3.json').read_text());folder=O/'forward'/m['run_id'];rule=dict(created_UTC=n.utc(n.nowus()),target_closed_ms=m['T0_ms']+900000,criterion='both symbols first full postT0 15m bar received/processed; NOT profit or strategy selection',maximum_wait_seconds=900)
(O/'observation_stop_rule.json').write_text(json.dumps(rule,indent=2));deadline=time.time()+900
while time.time()<deadline:
 p=folder/'checkpoint.pkl'
 if p.exists():
  with p.open('rb')as f:e=pickle.load(f)
  if all(e.legs[a]['last_close_ms']>=rule['target_closed_ms']for a in ['BTC','ETH']):
   (folder/'STOP_REQUESTED').write_text(json.dumps(dict(rule,requested_UTC=n.utc(n.nowus()),reason='data-quality milestone reached; financial path still halted on zero-NA')));print('STOP_REQUESTED_BOTH_CLOSED');break
 if(folder/'status.json').exists()and(folder/'STOP_REQUESTED').exists():break
 time.sleep(1)
