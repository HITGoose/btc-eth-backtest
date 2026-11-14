import online as n,json,time,pickle
from pathlib import Path
O=n.O

def main():
 t0=((int(time.time())+300)//900+1)*900000;folder=O/'preflight';folder.mkdir(exist_ok=True);events=[]
 sg=n.Signals(t0,folder)
 cached=folder/'warm_responses.json'
 if cached.exists():
  events=json.loads(cached.read_text())
  for q in events:sg.add(q['asset'],q['data'],q['received_us'])
 else:sg.warm(events.append)
 (folder/'warm_responses.json').write_text(json.dumps(events));legs=sg.calculate();manifest=dict(T0_ms=t0,run_id='PRE_FLIGHT_NOT_FORWARD')
 e=n.Engine(manifest,legs);e.audit();e.save(folder)
 (folder/'warm_responses.json').write_text(json.dumps(events));(folder/'summary.json').write_text(json.dumps(dict(proposed_T0_ms=t0,actual_last_closed={a:q['last_close_ms']for a,q in legs.items()},accounts=len(e.books),no_forward_trades=True)))
 for a,endpoint in [('BTC','trades'),('ETH','trades'),('BTC','premiumIndex'),('BTC','fundingRate')]:
  q=n.fetch(endpoint,symbol=a+'USDT',**({'limit':1000}if endpoint=='trades'else{}));(folder/(a+'_'+endpoint+'.json')).write_text(json.dumps(q));print(a,endpoint,str(q['data'])[:200],flush=True)
 print('PREFLIGHT_OK',t0)
if __name__=='__main__':main()
