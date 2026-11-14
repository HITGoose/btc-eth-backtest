import shared as s
import importlib.util
_report_spec=importlib.util.spec_from_file_location('extra_cost_readonly_report',s.OUT/'report.py')
r=importlib.util.module_from_spec(_report_spec);_report_spec.loader.exec_module(r)
assert r.__file__==str(s.OUT/'report.py') and hasattr(r,'PERIODS')
O=s.OUT;h=s.z.h;np=s.np

def main():
 summary=[];detail=[]
 for period in r.PERIODS:
  scenes=s.b.SCENARIOS if period=='2025'else['STRICT']
  for cost in ['C1','C2']:
   for group in ['B','I100','I50','I25']:
    for scene in scenes:
     loaded=[]
     for asset in ['BTC','ETH']:
      try:q0,m0=r.load(period,asset,cost,group,'F_TOUCH',scene);q1,m1=r.load(period,asset,cost,group,'F_THROUGH',scene)
      except FileNotFoundError:break
      meta=dict(period=period,scenario=scene,cost=cost,group=group,fill='F_THROUGH',comparison_base=group+'_F_TOUCH',scope='fill proxy sensitivity, not true queue fill probability')
      delta=r.attribution(q0,q1,meta);detail.extend(delta);loaded.append((q0,m0,q1,m1))
      mm0=h.metrics(q0['trades'],m0,500.,q0['window'],bool(q0['state_at_end']['position']));mm1=h.metrics(q1['trades'],m1,500.,q1['window'],bool(q1['state_at_end']['position']))
      summary.append(dict(meta,asset=asset,funding=q1['funding'],ending_TOUCH=q0['ending_equity'],ending_THROUGH=q1['ending_equity'],actual_difference_USDT=q1['ending_equity']-q0['ending_equity'],DD_TOUCH=mm0['max_drawdown_pct'],DD_THROUGH=mm1['max_drawdown_pct'],ADDED=sum(x['category']=='ADDED'for x in delta),DISAPPEARED=sum(x['category']=='DISAPPEARED'for x in delta),CHANGED=sum(x['category']=='CHANGED'for x in delta),entry_time_changed=sum(x['old_opened_us']is not None and x['new_opened_us']is not None and x['old_opened_us']!=x['new_opened_us']for x in delta)))
     if len(loaded)==2:
      old=np.asarray(loaded[0][1])+loaded[1][1];new=np.asarray(loaded[0][3])+loaded[1][3];m0=h.metrics(loaded[0][0]['trades']+loaded[1][0]['trades'],old,1000.,loaded[0][0]['window']);m1=h.metrics(loaded[0][2]['trades']+loaded[1][2]['trades'],new,1000.,loaded[0][2]['window'])
      summary.append(dict(meta,asset='COMBINED',funding=loaded[0][2]['funding'],ending_TOUCH=float(old[-1]),ending_THROUGH=float(new[-1]),actual_difference_USDT=float(new[-1]-old[-1]),DD_TOUCH=m0['max_drawdown_pct'],DD_THROUGH=m1['max_drawdown_pct']))
 r.write('fill_sensitivity.csv',summary);r.write('fill_trade_attribution.csv.gz',detail);print('FILL_SENSITIVITY',len(summary),len(detail))
if __name__=='__main__':main()
