"""Observation-only subclass; all financial methods delegate to frozen parent."""
import json,hashlib,copy
import numpy as np
import bridge as b

DIAGNOSTIC={'leg','_sensitivity_trace','_sensitivity_input','_sensitivity_window','_sensitivity_depth'}
def canonical(x):
 if isinstance(x,np.generic):return x.item()
 if isinstance(x,np.ndarray):return x.tolist()
 if isinstance(x,dict):return{str(k):canonical(v)for k,v in sorted(x.items(),key=lambda kv:str(kv[0]))}
 if isinstance(x,(list,tuple)):return[canonical(v)for v in x]
 if isinstance(x,set):return sorted(canonical(v)for v in x)
 if hasattr(x,'__dict__'):return canonical(vars(x))
 return x

def brief(book):
 names=['asset','exit_policy','cash','realized','order','position','order_info','replacement','stats','tranches','profile','fee','raw_sequence','_visit_side']
 return canonical({k:getattr(book,k,None)for k in names})
def full_state(book):return canonical({k:v for k,v in vars(book).items()if k not in DIAGNOSTIC})
def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(encoded(value)).hexdigest()

class TraceBook(b.pe.Book):
 def _capture(self,method,fn,*args,**kwargs):
  token=getattr(self,'_sensitivity_input',None);window=getattr(self,'_sensitivity_window',None)
  enabled=bool(token and window and window[0]<=token['time_us']<window[1] and not getattr(self,'_sensitivity_depth',0))
  if not enabled:return fn(*args,**kwargs)
  pre=brief(self);old_events=len(self.events);old_trades=len(self.journal);self._sensitivity_depth=1
  try:result=fn(*args,**kwargs)
  finally:self._sensitivity_depth=0
  self._sensitivity_trace.append(dict(method=method,input=copy.deepcopy(token),pre_state=pre,post_state=brief(self),events_generated=canonical(self.events[old_events:]),trades_generated=canonical(self.journal[old_trades:])))
  return result
 def visit(self,*args,**kwargs):return self._capture('visit',super().visit,*args,**kwargs)
 def update_ladder(self,*args,**kwargs):return self._capture('update_ladder',super().update_ladder,*args,**kwargs)
 def on_core(self,*args,**kwargs):return self._capture('on_core',super().on_core,*args,**kwargs)

def instrument(book,window):
 original=full_state(book);book.__class__=TraceBook;book._sensitivity_trace=[];book._sensitivity_input=None;book._sensitivity_window=window;book._sensitivity_depth=0
 assert full_state(book)==original,'instrumentation changed parent state'
 return book

def clone(book,leg):
 original=book.leg;book.leg=None
 try:result=copy.deepcopy(book)
 finally:book.leg=original
 result.leg=leg;return result
