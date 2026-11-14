"""Public REST raw-trade forward observer. No exchange order endpoints or keys.
Receipt-causal clocks; unresolved raw gaps/costs halt financial processing, never invent prices.
"""
from pathlib import Path
import sys,json,time,hashlib,urllib.request,urllib.parse,inspect,types,dataclasses,csv,pickle,os,math,datetime
from decimal import Decimal
R=Path('/workspace/btc-eth-backtest');O=Path(__file__).resolve().parent;OLD=R/'outputs/extra_sizing_cost_stress';sys.path.insert(0,str(OLD))
import shared as s
import funding_engine as F
import through_engine as T
np=s.np;r=s.r
BASE='https://www.binance.com/fapi/v1/'
def nowus():return time.time_ns()//1000
def utc(t):return datetime.datetime.fromtimestamp(t/1e6,datetime.timezone.utc).isoformat()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def fetch(endpoint,**params):
 url=BASE+endpoint+'?'+urllib.parse.urlencode(params)
 with urllib.request.urlopen(url,timeout=10)as f:raw=f.read()
 received=nowus();data=json.loads(raw);assert isinstance(data,(list,dict));return dict(endpoint=endpoint,url=url,received_us=received,SHA256=hashlib.sha256(raw).hexdigest(),data=data,raw_UTF8=raw.decode('utf-8'))
class ClosedLeg(r.model.Leg):
 def signals(self,settings,*,macd_crosses=None):
  active=self.squeeze[settings.lookback]<=settings.squeeze_threshold
  bullish,bearish=(self.histogram>0,self.histogram<0)if macd_crosses is None else(macd_crosses==1,macd_crosses==-1)
  buy=active&self.above_band&bullish&(self.up>=settings.aligned_lines);sell=active&self.below_band&bearish&(self.down>=settings.aligned_lines)
  assert not np.any(buy&sell);minimum=(self.start-self.first)//900000
  return {self.first+(int(i)+1)*900000:(1 if buy[i]else-1)for i in np.flatnonzero(buy|sell)if minimum<=i<len(buy)}
class Signals:
 def __init__(self,t0,folder):self.t0=t0;self.folder=folder;folder.mkdir(exist_ok=True);self.bars={a:{}for a in ['BTC','ETH']}
 def add(self,a,rows,received,confirmed_closed=False):
  last_open=max(int(b[0])for b in rows)if rows else -1
  for b in rows:
   assert len(b)>=7 and isinstance(b[0],int)and isinstance(b[6],int)
   if b[6]*1000>=received:continue # never receive a future close
   if not confirmed_closed and b[0]>=last_open:continue # REST terminal may be an old in-flight snapshot
   assert b[6]==b[0]+899999
   values=[Decimal(str(v))for v in b[1:6]];assert all(v.is_finite()for v in values)and min(values[:4])>0 and values[4]>=0
   old=self.bars[a].get(b[0]);assert old is None or (old[0]==b[0]and old[6]==b[6]and all(Decimal(str(x))==Decimal(str(y))for x,y in zip(old[1:6],b[1:6]))),'closed candle revision requires a new audit'
   self.bars[a][b[0]]=b
 def warm(self,write):
  start=self.t0//3600000*3600000-30*86400000-r.model.WARMUP
  for a in self.bars:
   cursor=start
   while True:
    q=fetch('klines',symbol=a+'USDT',interval='15m',startTime=cursor,limit=1500);write(dict(type='PREWARM',asset=a,**q));self.add(a,q['data'],q['received_us']);rows=q['data'];assert rows
    end=(q['received_us']//1000//900000)*900000
    cursor=rows[-1][0]
    if cursor>=end:break
 def calculate(self):
  result={}
  prior=json.loads(r.selected.FAST_WINDOW_REPORT.read_text());policy=r.RegimeOverlay(**prior['policy']);pair=tuple(tuple(v)for v in prior['cases'][r.selected.MODE]['er_windows_and_thresholds'])
  for a,bars in self.bars.items():
   end=max(bars)+900000;path=self.folder/(a+'_closed.csv')
   with path.open('w',newline='')as f:
    w=csv.writer(f);w.writerow(['timestamp','open','high','low','close','volume']);w.writerows([b[:6]for _,b in sorted(bars.items())])
   leg=r.model.build(path,self.t0//3600000*3600000-30*86400000,end)
   # Batch API drops a terminal row reserved for the next minute's submission.
   # Online input contains CLOSED rows only: evaluate terminal CLOSED row itself.
   object.__setattr__(leg,'__class__',ClosedLeg)
   branches={};contexts={}
   for threshold in [.25,.30]:
    fn=s.z.s.clone_schedule(threshold if a=='ETH'else .25)
    src=inspect.getsource(r.regime.market_schedules).replace('range(32, len(closes) - 1)','range(32, len(closes))')
    ns=dict(fn.__globals__);exec(src,ns);schedule,ctx=ns['market_schedules'](a,leg,price_file=path,include_gate_confirmation=True,regime_thresholds=pair,use_entry_crosses=False)
    pol=dataclasses.replace(policy,range_squeeze_pct=threshold if a=='ETH'else .25);branches[threshold]=r.stacked_signals(schedule['baseline'],ctx,pol);contexts[threshold]=ctx
   result[a]=dict(leg=leg,core=branches[.25],wide=branches[.30],contexts=contexts,last_close_ms=end)
  return result
class LiveBook(T.FundBook):
 def submit_core(self,request,time_us):return super().submit_core(request,max(time_us,getattr(self,'observed_clock_us',time_us)))
class Engine:
 def __init__(self,manifest,signals):
  self.manifest=manifest;self.t0=manifest['T0_ms'];self.books={};self.legs=signals;self.latest={};self.lastid={};self.raw_records={};self.last_clock=self.t0*1000-1;self.pending=[];self.seen_signals=set();self.halts=[];self.funding_due={};self.known_funding={};self.marks=[];self.events=[];self.last_seen=0;self.raw_count=0;self.pending_v2=set()
  for fill in ['F_TOUCH','F_THROUGH']:
   for g in ['B','I100','I50','I25']:
    for a in ['BTC','ETH']:
     parent,ratio=s.GROUPS[g];x=s.b.pe.book(a,.0005,signals[a]['leg'],signals[a]['core'],a=='ETH'and g!='B');x.__class__=LiveBook
     x.extra_ratio=ratio;x.fill_mode=fill;x.slippage=.0002;x.sizing_audit=[];x.slippage_cost=0.;x.funding_total=0.;x.funding_events=[];x.last_funding_ms=-1;x.funding_feed=[];x.funding_cursor=0
     self.books[(fill,g,a)]=x
 def event(self,event,**kw):
  row=dict(event=event,received_us=self.last_seen);row.update(kw);self.events.append(row)
 def halt(self,reason,**kw):
  self.halts.append(dict(reason=reason,received_us=self.last_seen,**kw));self.event('FINANCIAL_HALT',reason=reason,**kw)
 def activate(self,x,t):s.activate(x);x.audit_timestamp=t/1e6;x.observed_clock_us=t
 def no_v2_reason(self,x,t):
  pos=x.position
  if not pos or x.order_info.get('origin')!='EXTRA':return None
  if getattr(pos,'adaptive_v2_used',False):return 'ALREADY_USED'
  if pos.partial_queue:return 'ALREADY_QUEUED'
  i=(t*1000-x.leg.first)//900000-1
  if i<1 or i>=len(x.leg.histogram):return 'NOT_EVALUATED_CLOSED_BAR_UNAVAILABLE'
  side=pos.order.side;aligned=x.leg.up if side==1 else x.leg.down
  if not all(aligned[j]!=6 and side*x.leg.histogram[j]<=0 for j in [i,i-1]):return 'TWO_CLOSED_BARS_NOT_WEAK'
  price=x.leg.bars[t*1000-900000].c;distance=side*(price-pos.stop)
  if distance<=0:return 'STOP_PRIORITY'
  if pos.order.qty*distance<=max(0.,x.cash)*.03:return 'REMAINING_REFERENCE_RISK_WITHIN_UNSCALED_3PCT_BUDGET'
  return 'LOT_ROUNDING_OR_CAP_LIMIT'
 def advance(self,t):
  if t<self.t0*1000:return
  if self.halts:return
  if t<self.last_clock:self.halt('ACTOR_CLOCK_REVERSED',clock_us=t);return
  for a,due in self.funding_due.items():
   if self.last_clock<due*1000<=t and(a,due)not in self.known_funding:self.halt('EXACT_SETTLEMENT_COST_PENDING',asset=a,time_ms=due);return
  clocks=[];first=self.last_clock//1000000+1
  for sec in range(first,t//1000000+1):
   if sec%5==2:clocks.append((sec*1000000,'POLL',None))
   if sec%900==0:clocks.append((sec*1000000,'V2',None))
   if sec%60==0:clocks.append((sec*1000000,'MARK',None))
  clocks += [(p['due_us'],'SUBMIT',p)for p in self.pending if self.last_clock<p['due_us']<=t]
  clocks.sort(key=lambda x:(x[0],{'V2':0,'SUBMIT':1,'POLL':2,'MARK':3}[x[1]]))
  for clock,kind,p in clocks:
   for (fill,g,a),x in self.books.items():
    self.activate(x,clock);r.seconds.expire(x,clock/1e6)
    if kind=='V2':
     if self.legs[a]['last_close_ms']>=clock//1000:
      count=len(x.events);s.b.e.x.check_trend(x,clock//1000000)
      if x.position and any(e['event']=='adaptive_v2_request'for e in x.events[count:]):x.position.partial_requested_effective_us=clock
      elif g=='I25':
       reason=self.no_v2_reason(x,clock//1000000)
       if reason:self.event('I25_EXTRA_V2_NOT_REQUESTED',fill=fill,asset=a,time_us=clock,reason=reason,budget=max(0.,x.cash)*.03)
     else:self.pending_v2.add((a,clock))
    elif kind=='POLL'and a in self.latest:
     before=x.position.stop if x.position else None;x.update_ladder(self.latest[a]['price'])
     if x.position and before!=x.position.stop:x.last_stop_activation_us=clock
    elif kind=='SUBMIT'and a==p['asset']:
     if p['directions'].get(g) is None:continue
     if t-clock>1000000:self.halt('MISSED_SUBMISSION_DEADLINE',signal=p['stamp']);return
     side=p['directions'][g];actual=max(clock,t);self.activate(x,actual)
     if x.priority and x.core.get(p['stamp'])==side:
      x.on_core(p['stamp'],p['ref'],side)
      if x.replacement:x.replacement['requested_us']=actual
     elif not(x.position or x.order or x.replacement):
      x.submitting_signal=p['stamp']
      try:x.place(actual/1000,p['ref'],side,nearest_tick=True)
      finally:x.submitting_signal=None
    elif kind=='MARK':
     price=self.latest.get(a,{}).get('price');eq=x.equity(price)if price is not None else x.cash
     self.marks.append(dict(time_us=clock,fill=fill,group=g,asset=a,equity=eq,cash=x.cash,cost_status='KNOWN_THROUGH_VERIFIED_CUTOFF'))
   self.last_clock=clock
  self.pending=[p for p in self.pending if p['due_us']>t];self.last_clock=t
 def update_signals(self,signals,received):
  self.legs=signals
  if self.halts:return
  for (fill,g,a),x in self.books.items():x.leg=signals[a]['leg'];x.core=signals[a]['core']
  for a,clock in sorted(self.pending_v2.copy()):
   if signals[a]['last_close_ms']>=clock//1000:
    for (fill,g,asset),x in self.books.items():
     if asset!=a:continue
     self.activate(x,received);before=len(x.events);s.b.e.x.check_trend(x,clock//1000000)
     for e in x.events[before:]:
      e.update(closed_candle_received_us=received,effective_request_us=received)
      if e['event']=='adaptive_v2_request'and x.position:x.position.partial_requested_effective_us=received
    for (fill,g,asset),x in self.books.items():
     if asset==a and g=='I25'and not any(e['event']=='adaptive_v2_request'and e['time_us']==clock for e in x.events):
      reason=self.no_v2_reason(x,clock//1000000)
      if reason:self.event('I25_EXTRA_V2_NOT_REQUESTED',fill=fill,asset=a,time_us=clock,reason=reason,budget=max(0.,x.cash)*.03)
    self.pending_v2.remove((a,clock))
  for a in ['BTC','ETH']:
   stamp=signals[a]['last_close_ms']
   if stamp<=self.t0 or (a,stamp)in self.seen_signals:continue
   if a=='ETH'and signals['BTC']['last_close_ms']<stamp:self.event('WAIT_BTC_CLOSED_CANDLE');continue
   self.seen_signals.add((a,stamp))
   info=signals[a];directions={}
   for g in ['B','I100','I50','I25']:
    parent=s.GROUPS[g][0];d,diag=s.z.classify(info['core'],info['wide'],signals['BTC']['core'],parent);directions[g]=d.get(stamp)
   self.event('SIGNAL_EVALUATION',asset=a,signal_close_ms=stamp,core=info['core'].get(stamp),wide=info['wide'].get(stamp),BTC_complete_signal=signals['BTC']['core'].get(stamp),directions=directions,contexts={str(k):v.get(stamp)for k,v in info['contexts'].items()},I25_V2_budget_not_scaled=True)
   if any(directions.values()):
    if received>stamp*1000+10000000:self.halt('CLOSED_CANDLE_RECEIVED_AFTER_ORDER_DEADLINE',asset=a,signal=stamp);return
    self.pending.append(dict(asset=a,stamp=stamp,due_us=stamp*1000+10000000,ref=info['leg'].bars[stamp-900000].c,directions=directions))
 def consume(self,q):
  self.last_seen=q['received_us'];at=q.get('available_to_sim_us',q['received_us']);self.advance(at)
  a=q.get('asset');typ=q['type']
  if typ=='TRADES':
   rows=q['data'];assert isinstance(rows,list)and rows
   rows=sorted(rows,key=lambda x:int(x['id']))
   for raw in rows:
    assert type(raw['id'])is int and type(raw['time'])is int,'raw identifiers/timestamps must be integers'
    ident=int(raw['id']);et=int(raw['time'])*1000;price=float(raw['price']);assert price>0 and et<=q['received_us']+2000000
    prev=self.lastid.get(a)
    if prev is not None and ident<=prev:
     prior=self.raw_records.get(a,{}).get(ident)
     if prior is not None and prior!=raw:self.halt('RAW_ID_CONFLICT',asset=a,id=ident)
     continue
    if prev is not None and ident!=prev+1:self.halt('RAW_TRADE_ID_GAP',asset=a,previous=prev,current=ident)
    self.raw_records.setdefault(a,{})[ident]=raw
    if len(self.raw_records[a])>5000:self.raw_records[a]={i:v for i,v in self.raw_records[a].items()if i>ident-5000}
    self.lastid[a]=ident;self.raw_count+=1;self.latest[a]=dict(price=price,event_us=et,received_us=q['received_us'],id=ident)
    if et<self.t0*1000 or self.halts:continue
    relevant=[x for key,x in self.books.items()if key[2]==a]
    unsafe=any(x.position and et<getattr(x,'last_stop_activation_us',self.t0*1000)and x.position.order.side*(price-x.position.stop)<=0 for x in relevant)
    if unsafe:self.halt('LATE_PRINT_REQUIRES_EVENT_HISTORY_REPLAY',asset=a,id=ident);continue
    for(fill,g,asset),x in self.books.items():
     if asset!=a:continue
     self.activate(x,at);x.current_raw_id=ident
     if x.order and et<x.order_info['submitted_us']:continue
     if x.position and et<getattr(x,'last_stop_activation_us',self.t0*1000)and x.position.order.side*(price-x.position.stop)<=0:self.halt('LATE_PRINT_BEFORE_STOP_ACTIVATION',asset=a,id=ident);break
     old_request=x.replacement
     crosses_stop=bool(x.position and x.position.order.side*(price-x.position.stop)<=0)
     suppress_replace=bool(old_request and et<=old_request['requested_us']and not crosses_stop)
     queue=x.position.partial_queue if x.position else None
     suppress_partial=bool(queue and et<getattr(x.position,'partial_requested_effective_us',self.t0*1000))
     if suppress_replace:x.replacement=None
     if suppress_partial:x.position.partial_queue=[]
     try:
      count=len(x.events);x.visit(price,at//1000,True,advance_ladder=False)
      for ev in x.events[count:]:ev.update(exchange_event_us=et,network_received_us=q['received_us'],available_to_sim_us=at)
     finally:
      if suppress_replace and x.position:x.replacement=old_request
      if suppress_partial and x.position:x.position.partial_queue=queue
  elif typ=='PREMIUM':
   assert q['data']['symbol']==a+'USDT';due=int(q['data']['nextFundingTime']);assert due>0;self.funding_due[a]=due
  elif typ=='FUNDING':
   for row in q['data']:
    t=int(row['fundingTime'])
    if t<self.t0:continue
    mark=row.get('markPrice');
    if not mark:self.event('COST_PRICE_MISSING',asset=a,time_ms=t);continue
    self.known_funding[(a,t)]=row
    if self.halts:continue
    if t*1000<self.last_clock and any(x.position for k,x in self.books.items()if k[2]==a):self.halt('LATE_FUNDING_REQUIRES_LABELLED_REPLAY',asset=a,time_ms=t);continue
    for k,x in self.books.items():
     if k[2]==a and t>x.last_funding_ms:self.activate(x,q['received_us']);x.settle(dict(time_ms=t,mark_price=float(mark),rate=float(row['fundingRate']),complete=True,source='BINANCE_USDT_PERPETUAL_OFFICIAL',received_us=q['received_us']))
 def audit(self):
  for x in self.books.values():F.cash_check(x)
 def save(self,folder):
  self.audit();p=folder/'checkpoint.tmp'
  with p.open('wb')as f:pickle.dump(self,f,protocol=5)
  p.replace(folder/'checkpoint.pkl')
  summary=dict(T0_ms=self.t0,last_received_UTC=utc(self.last_seen)if self.last_seen else None,verified_account_clock_UTC=utc(self.last_clock)if self.last_seen>=self.t0*1000 else None,halts=self.halts,raw_unique_trades=self.raw_count,simulated_orders=sum(x.stats['submitted']for x in self.books.values()),trades=sum(len(x.journal)for x in self.books.values()),status='FINANCIAL_HALTED'if self.halts else'WAITING_T0'if self.last_seen<self.t0*1000 else'OBSERVED_REALTIME_SIMULATION',fees_assumed=True,no_real_orders=True)
  (folder/'status.json').write_text(json.dumps(summary,indent=2))
