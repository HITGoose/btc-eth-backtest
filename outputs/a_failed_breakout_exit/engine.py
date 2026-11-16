from pathlib import Path
import sys
R=Path('/workspace/btc-eth-backtest');sys.path.insert(0,str(R/'outputs/adaptive_density_floors'));import experiment as parent
E=parent.E;sig=parent.sig;s=parent.s;np=parent.np;BAR_US=900000000;FOUR_HOURS_US=14400000000

def due_second(opened_us):return((int(opened_us)+FOUR_HOURS_US+BAR_US-1)//BAR_US)*900
class FailedBook(E.Book):
 def visit(self,price,t,at_open,**kw):
  old=self.position;request=self.fail_request
  # Original visit checks stop first, at the exact same model price/event.
  super().visit(price,t,at_open,**kw)
  if old is None and self.position is not None:
   p=self.position;p.fail_check_due_s=due_second(p.opened_us);p.fail_checked=False
  if request and old is not None and self.position is old and self.fail_request is request and self.audit_timestamp>=request['ready_s']:
   assert self.audit_timestamp>request['check_s'];self.close(price,'failed_breakout_exit',t)
 def close(self,price,reason,t):
  request=self.fail_request
  super().close(price,reason,t)
  if request:
   check=self.exit_checks[request['record_index']];status='EXECUTED'if reason=='failed_breakout_exit'else'ORIGINAL_EXIT_FIRST';check.update(request_status=status,exit_us=round(self.audit_timestamp*1e6),actual_reason=reason,actual_trigger_price=float(price),actual_exit_net=self.journal[-1]['net']);self.journal[-1].update(failed_check_ms=request['check_s']*1000,failed_exit_ready_ms=request['ready_s']*1000,failed_request_status=status)
  self.fail_request=None
 def check_closed(self,t):
  p=self.position
  if not self.fail_enabled or p is None or t%900 or getattr(p,'fail_checked',False)or t<getattr(p,'fail_check_due_s',float('inf')):return
  assert t==p.fail_check_due_s;p.fail_checked=True;i=(t*1000-self.band_first)//900000-1;assert i>=1 and i<len(self.closes);assert self.band_first+(i+1)*900000==t*1000
  c=float(self.closes[i]);inside=[];bars=[]
  for j in [i-1,i]:
   lo=float(self.band_low[j]);hi=float(self.band_high[j]);close=float(self.closes[j]);assert np.isfinite([lo,hi,close]).all();ok=lo<=close<=hi;inside.append(ok);bars.append(dict(bar_close_ms=self.band_first+(j+1)*900000,close=close,band_low=lo,band_high=hi,inside=ok))
  gross=p.order.side*(c-p.order.price)*p.order.qty;trigger=bool(gross<0 and all(inside));row=dict(signal_close_ms=self.order_info['signal_close_ms'],side=p.order.side,opened_us=p.opened_us,check_ms=t*1000,holding_us=t*1000000-p.opened_us,decision_close=c,entry=p.order.price,quantity=p.order.qty,gross_USDT=gross,two_closed_bars=bars,trigger=trigger,request_status='PENDING_NEXT_MINUTE'if trigger else'NOT_TRIGGERED_NO_RECHECK');self.exit_checks.append(row)
  if trigger:self.fail_request=dict(check_s=t,ready_s=t+60,record_index=len(self.exit_checks)-1)

def book(asset,fee,leg,core,closes,low,high,enabled=True):
 x=E.book(asset,fee,leg,core,False);x.__class__=FailedBook;x.exit_policy='fixed';x.fail_request=None;x.exit_checks=[];x.fail_enabled=enabled;x.closes=closes;x.band_low=low;x.band_high=high;x.band_first=leg.first if leg else 0;return x
