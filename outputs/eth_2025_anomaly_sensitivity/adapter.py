"""SHA/venue/day/record-scoped derived views; all other dates use frozen strict cache."""
from datetime import datetime,timezone
from pathlib import Path
import json,hashlib
import numpy as np
import bridge as b

def validate_gate(asset,day,sha,manifest):
 assert asset==manifest['allowed_asset']==b.ASSET
 assert day==manifest['allowed_UTC_date']==b.DAY
 assert sha==manifest['allowed_file_SHA256']==b.EXPECTED_SHA
 assert manifest['allowed_symbol']==b.SYMBOL and manifest['duplicate_ids']=={str(x):2 for x in b.IDS}
 assert manifest['rows']==7454972 and manifest['confirmed_timestamp_reversals']==2
 assert manifest['confirmed_quote_issue_lines']==[1493267,1513648,7261393]
 assert manifest['additional_findings']['decision']=='ID_HYPOTHESES_ELIGIBLE_WITH_ADDITIONAL_UNMODELED_FINDINGS'

class Views:
 def __init__(self):
  self.manifest=json.loads((b.OUT/'whitelist_manifest.json').read_text());self.folder=b.OUT/'raw_audit';self.views={}
  sha=hashlib.file_digest(b.ARCHIVE.open('rb'),'sha256').hexdigest();validate_gate(b.ASSET,b.DAY,sha,self.manifest)
  assert hashlib.sha256((self.folder/'audit.json').read_bytes()).hexdigest()==self.manifest['audit_JSON_SHA256']
  for name,expected in self.manifest['parsed_arrays_SHA256'].items():assert hashlib.sha256((self.folder/(name+'.npy')).read_bytes()).hexdigest()==expected,name
  self.ids=np.load(self.folder/'id.npy',mmap_mode='r');self.time_ms=np.load(self.folder/'time_ms.npy',mmap_mode='r');self.price=np.load(self.folder/'price.npy',mmap_mode='r');self.n=len(self.ids)
  assert self.ids.dtype==np.int64 and self.time_ms.dtype==np.int64 and self.n==self.manifest['rows']
  self.sorted=np.argsort(self.time_ms,kind='stable');self.pairs={x['trade_id']:[v['source_line']-2 for v in x['records']]for x in self.manifest['conflicts']}
  for trade,indices in self.pairs.items():
   assert len(indices)==2 and all(int(self.ids[i])==trade for i in indices)
   assert self.time_ms[indices[0]]<self.time_ms[indices[1]]
 def get(self,scenario):
  assert scenario in b.SCENARIOS,'unknown sensitivity hypothesis'
  if scenario in self.views:return self.views[scenario]
  drop=[]
  if scenario!='S_ALL':
   bits=scenario[2:]
   for trade,bit in zip(b.IDS,bits):drop.append(self.pairs[trade][1-int(bit)])
  keep=~np.isin(self.sorted,np.asarray(drop,dtype=np.int64));indices=self.sorted[keep]if drop else self.sorted
  rows=np.column_stack((self.time_ms[indices]/1000.,self.ids[indices],self.price[indices]));lines=indices+2
  assert len(rows)==self.n-(3 if drop else 0)
  assert np.array_equal(rows[:,1].astype(np.int64),self.ids[indices]);assert np.array_equal(np.rint(rows[:,0]*1000).astype(np.int64),self.time_ms[indices])
  assert np.all(np.diff(rows[:,0])>=0)
  meta=dict(scenario=scenario,status='SENSITIVITY_HYPOTHESIS_NOT_OFFICIAL_REPAIR',original_SHA256=b.EXPECTED_SHA,original_rows=self.n,derived_rows=len(rows),dropped_original_lines=[i+2 for i in drop],retained_conflict_lines={str(x):[i+2 for i in self.pairs[x]if i not in drop]for x in b.IDS},stable_integer_time_order=True,ties_use_original_source_line=True,ID_price_qty_quote_time_unchanged=True,ordered_original_line_SHA256=hashlib.sha256(lines.tobytes()).hexdigest())
  result=dict(rows=rows,lines=lines,indices=indices,metadata=meta);self.views[scenario]=result;return result
 def identity(self,scenario,index):
  v=self.get(scenario);i=int(v['indices'][index]);return dict(original_source_line=i+2,original_trade_id=int(self.ids[i]),timestamp_integer=int(self.time_ms[i]),time_unit='ms',price=float(self.price[i]),internal_event_id=b.EXPECTED_SHA+':line:'+str(i+2))
 def latest(self,scenario,second):
  v=self.get(scenario);i=int(np.searchsorted(v['rows'][:,0],second,side='right'))-1
  if i<0:return None
  return self.identity(scenario,i)
 def equivalence_proof(self):
  m=self.manifest;pre=m['fork_second'];post=m['merge_second'];prefix=None;suffix=None;quotes=None;reports=[]
  for name in b.SCENARIOS:
   v=self.get(name);rows=v['rows'];lo=int(np.searchsorted(rows[:,0],pre,side='left'));hi=int(np.searchsorted(rows[:,0],post,side='left'));a=v['lines'][:lo];s=v['lines'][hi:];q=self.latest(name,post-0.000001)
   if prefix is None:prefix=a;suffix=s;quotes=q
   else:assert np.array_equal(prefix,a)and np.array_equal(suffix,s)and q==quotes
   reports.append(dict(scenario=name,prefix_rows_before_fork=lo,suffix_rows_at_merge=len(s),prefix_SHA256=hashlib.sha256(a.tobytes()).hexdigest(),suffix_SHA256=hashlib.sha256(s.tobytes()).hexdigest(),latest_quote_before_merge=q,view=v['metadata']))
  proof=dict(fork_second=pre,merge_second=post,all_prefix_original_events_identical=True,all_suffix_original_events_identical=True,all_latest_quotes_identical_at_merge=True,scenarios=reports)
  b.dump(b.OUT/'view_equivalence.json',proof);return proof

class ScenarioCache:
 def __init__(self,strict,views,scenario):self.strict=strict;self.views=views;self.scenario=scenario
 def load(self,minute):
  day=datetime.fromtimestamp(minute,timezone.utc).strftime('%Y-%m-%d')
  if self.strict.asset==b.ASSET and day==b.DAY:return self.views.get(self.scenario)['rows']
  return self.strict.load(minute)

class Market(b.pe.Market):
 def __init__(self,native,cache,book,optimized=True):
  super().__init__(native,cache,book,optimized);self.mark_access_days=set();self.event_access_days=set();self.last_poll=None
 def __getitem__(self,minute):
  self.mark_access_days.add(datetime.fromtimestamp(minute,timezone.utc).strftime('%Y-%m-%d'))
  return super().__getitem__(minute)
 def events(self,minute,phase,*,side=None,poll_seconds=5):
  day=datetime.fromtimestamp(minute,timezone.utc).strftime('%Y-%m-%d');self.event_access_days.add(day)
  gen=super().events(minute,phase,side=side,poll_seconds=poll_seconds)
  for stamp,price,poll in gen:
   token=dict(time_us=round(stamp*1e6),price=float(price),kind='POLL'if poll is True else'CORE_CLOCK'if poll else'RAW',source_day=day)
   if day==b.DAY:
    view=self.cache.views
    if poll is False:
     index=int(gen.gi_frame.f_locals['i']);token.update(view.identity(self.cache.scenario,index))
    else:
     quote=view.latest(self.cache.scenario,stamp)
     token['latest_real_quote']=quote
   elif poll is False:token['original_trade_id']=self.book.current_raw_id
   self.book._sensitivity_input=token
   if poll is True:self.last_poll=dict(token)
   yield stamp,price,poll
