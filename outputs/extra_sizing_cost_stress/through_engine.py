"""F_THROUGH changes only price qualification; preserves original submission clock."""
import hashlib,json
import shared as s
import cost_engine as C
import funding_engine as F
FULL=False;COST='C1'
class ClockMixin:
 def place(self,*args,**kwargs):
  result=super().place(*args,**kwargs)
  if self.order:
   # time_us/Order.time is original+10s or actual completed CORE replacement.
   # observed/effective_submission_us is an audit check, not an extra delay.
   self.order.submitted_effective_us=self.order_info['submitted_us']
  return result
class NoFundBook(ClockMixin,C.Book):pass
class FundBook(ClockMixin,F.Book):pass

def configure_feed(period,asset):
 global FULL,COST
 path=s.OUT/'funding_data'/period/asset/'result.json';d=json.loads(path.read_text());FULL=d['status']=='COMPLETE';COST='C2'if FULL else'C1'
 if FULL:F.configure_feed(period,asset)
 s.b.e.x.check_trend=F.funding_check if FULL else F.original_check
 return hashlib.file_digest(path.open('rb'),'sha256').hexdigest()

def book(*args,**kwargs):
 x=(F.book if FULL else C.book)(*args,**kwargs);x.__class__=FundBook if FULL else NoFundBook
 x.submission_clock_policy='ORIGINAL_SUBMITTED_US; audit observation never delays an eligible event'
 return x

def Market(*args,**kwargs):return(F.Market if FULL else C.Market)(*args,**kwargs)
def cash_check(x):return(F.cash_check if isinstance(x,FundBook)else C.cash_check)(x)
