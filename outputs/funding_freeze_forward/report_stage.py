"""Read-only cost report and independent accounting audit. No selection/optimization."""
from pathlib import Path
import json,hashlib,csv,gzip,importlib.util,zipfile,sys
import online as n
O=n.O;OLD=n.OLD;s=n.s;np=n.np
sp=importlib.util.spec_from_file_location('reference_cost_report',OLD/'report.py');ref=importlib.util.module_from_spec(sp);sp.loader.exec_module(ref)
def csvout(name,rows):
 if rows:s.z.csv_dump(O/name,rows)
def audit(q,mode=None):
 rows=ref.rows(q);fee=q['fee'];turnover=0.;fund=0.
 for t in rows:
  side=1 if t['side']=='LONG'else-1;entry=t['entry'];qty=t['quantity'];parts=t.get('partial_fills',[]);left=t['final_exit_quantity']
  assert abs(qty-left-sum(f['quantity']for f in parts))<1e-8
  turnover+=entry*qty+sum(f['execution_price']*f['quantity']for f in parts)
  pg=sum(side*(f['execution_price']-entry)*f['quantity']-fee*f['execution_price']*f['quantity']for f in parts)
  funding=0.;events=[]
  if mode or q.get('funding')=='INCLUDED_OFFICIAL':
   feed=json.loads((O/'funding_feeds'/q['period']/q['asset']/'result.json').read_text())['feeds'][mode]if mode else json.loads((OLD/'funding_data'/q['period']/q['asset']/'result.json').read_text())['events']
   for e in feed:
    us=e['time_ms']*1000
    if t['opened_us']<us<=(t.get('closed_us')or s.z.h.us(q['window'][1])-1):
     remaining=qty-sum(f['quantity']for f in parts if f['time_us']<us);delta=-side*remaining*e['mark_price']*e['rate'];funding+=delta;events.append((us,remaining,delta))
   fund+=funding
  if t['status']=='CLOSED':
   turnover+=t['exit']*left;expected=pg+side*(t['exit']-entry)*left-fee*(entry*qty+t['exit']*left)+funding
   assert abs(expected-t['net'])<1e-7,('closed net',q['key'],t['signal_close_ms'])
   if mode or q.get('funding')=='INCLUDED_OFFICIAL':assert abs(funding-t['funding_net_USDT'])<1e-7
  else:
   expected=pg-fee*entry*qty+side*(q['actual_raw_last_mark']-entry)*left+funding
   assert abs(expected-q['open_contribution'])<1e-7
 assert abs(q['stats'].get('fees',0)-turnover*fee)<1e-7
 assert abs(q['cash']-500-sum(e['delta']for e in q['cash_events']))<1e-7
 assert abs(q['ending_equity']-500-sum(t['net']for t in q['trades'])-q['open_contribution'])<1e-7
 if mode or q.get('funding')=='INCLUDED_OFFICIAL':assert abs(fund-q['funding_total_USDT'])<1e-7
 return dict(period=q['period'],asset=q['asset'],key=q['key'],funding_mode=mode or q.get('funding'),cash=q['cash'],ending_equity=q['ending_equity'],independent_funding_USDT=fund,fees_USDT=turnover*fee,passed=True)
def main():
 for name,sha in {**json.loads((OLD/'frozen_code.json').read_text()),**json.loads((OLD/'frozen_funding_code.json').read_text())}.items():assert hashlib.sha256((OLD/name).read_bytes()).hexdigest()==sha
 native=json.loads((OLD/'native_input_manifest.json').read_text())
 for item in native['native_inputs']:
  for f in item['files']:assert hashlib.file_digest(open(f['path'],'rb'),'sha256').hexdigest()==f['SHA256']
 (O/'reference_source_validation.json').write_text(json.dumps(dict(old_financial_sources_unchanged=True,native_files_SHA256_passed=32,reference_base='02608460c21e1f29db7191cffc58fd8f8c0632b4',new_replay_not_claimed_for_references=True)))
 result=[];availability=[];audits=[];attrs=[];references=[];unique={};monthly=[]
 for period in ['2020','2021','2022','2023','2024','2025','2026','NOV']:
  modes=['C1','OPEN','HIGH','LOW']if period in('2020','2021','2022','2023')else['C1','C2_REFERENCE']
  for mode in modes:
   for g in ['B','I100','I50','I25']:
    pair=[];scene='S_ALL'if period=='2025'else'STRICT';meta=dict(period=period,group=g,cost=mode,scenario=scene,fill='F_TOUCH')
    try:
     for a in ['BTC','ETH']:
      if mode in ['OPEN','HIGH','LOW']:
       folder=O/'historical/runs'/period/a/'funded';assert json.loads((folder/'status.json').read_text())['completed'];key='APPROX_'+mode+'_'+(g if a=='ETH'else'B')+'_F_TOUCH';p=folder/'results/STRICT'/(key+'_result.json');q=json.loads(p.read_text());m=np.load(p.with_name(key+'_equity.npz'))['marks'];assert q['funding']=='APPROXIMATE_FUNDING'
       assert q['funding_data_SHA256']==hashlib.sha256((O/'funding_feeds'/period/a/'result.json').read_bytes()).hexdigest()
      else:q,m=ref.load(period,a,'C1'if mode=='C1'else'C2',g,'F_TOUCH',scene)
      identity=(period,a,mode,g if a=='ETH'else'B')
      if identity not in unique:
       audits.append(audit(q,mode if mode in ['OPEN','HIGH','LOW']else None));unique[identity]=q
       if mode in ['C1','C2_REFERENCE']:references.append(dict(period=period,asset=a,mode=mode,group=g if a=='ETH'else'B',base_commit='02608460c21e1f29db7191cffc58fd8f8c0632b4',canonical_result_SHA256=n.digest(q),minute_values_SHA256=hashlib.sha256(m.tobytes()).hexdigest(),new_replay_claimed=False))
      assert abs(float(m[-1])-q['ending_equity'])<1e-8;pair.append((q,m))
    except (OSError,AssertionError)as e:availability.append(dict(meta,status='UNVERIFIED',error=repr(e)));continue
    status='APPROXIMATE_FUNDING'if mode in ['OPEN','HIGH','LOW']else'REFERENCE_COMPLETED_WITH_DATA_ANOMALY'if period=='2025'else'REFERENCE_VERIFIED_NOT_NEW_REPLAY';availability.append(dict(meta,status=status))
    for a,ts,marks,initial in [('BTC',pair[0][0]['trades'],pair[0][1],500.),('ETH',pair[1][0]['trades'],pair[1][1],500.),('COMBINED',pair[0][0]['trades']+pair[1][0]['trades'],pair[0][1]+pair[1][1],1000.)]:
     metric=s.z.h.metrics(ts,marks,initial,pair[0][0]['window'],sum(bool(q['state_at_end']['position'])for q,m in pair if a=='COMBINED'or q['asset']==a));months=metric.pop('monthly');result.append(dict(meta,asset=a,status=status,**metric));monthly.extend(dict(meta,asset=a,**r)for r in months)
    if g!='B':
     try:
      if mode in ['OPEN','HIGH','LOW']:base=unique[(period,'ETH',mode,'B')]
      else:base=ref.load(period,'ETH','C1'if mode=='C1'else'C2','B','F_TOUCH',scene)[0]
      attrs+=ref.attribution(base,pair[1][0],dict(meta,comparison_base='B'))
     except KeyError:pass
 for p in ['2020','2021','2022','2023']:
  for g in ['B','I100','I50','I25']:availability.append(dict(period=p,group=g,cost='C2_EXACT',status='UNVERIFIED',error='Official exact settlement markPrice missing; estimates kept separate'))
 csvout('historical_costs.csv',result);csvout('historical_monthly.csv',monthly);csvout('historical_availability.csv',availability);csvout('historical_trade_matching.csv.gz',attrs)
 (O/'historical_accounting_audit.json').write_text(json.dumps(dict(passed=True,accounts=len(audits),checks=audits),indent=2));(O/'reference_proof.json').write_text(json.dumps(references,indent=2))
 A=O/'artifacts';A.mkdir(exist_ok=True)
 for p in ['2020','2021','2022','2023','2024','2025','2026','NOV']:
  with zipfile.ZipFile(A/('ledgers_'+p+'.zip'),'w',zipfile.ZIP_DEFLATED)as z:
   for identity,q in unique.items():
    if identity[0]==p:z.writestr('_'.join(identity)+'.json',json.dumps(q))
 text=['# 历史资金费成本证据','', '严格精确C2：2020—2023仍UNVERIFIED。官方fundingRate缺价没有被“修复”；以下OPEN/HIGH/LOW只对缺失部分使用该结算分钟官方markPrice开盘/高/低，已知精确值保留。高低包含回顾信息，仅用于资金费误差敏感性，不进信号，也不是账户收益严格上下界。','', 'C1及2024—2026/NOV是验证同配置后的旧结果引用，不冒充本轮重放；2025保留数据异常标签。各年各币500独立起算。','', '|区间|版本|C1收益%|估算OPEN%|HIGH%|LOW%|OPEN回撤%|','|---|---|---:|---:|---:|---:|---:|']
 for p in ['2020','2021','2022','2023']:
  for g in ['B','I100','I50','I25']:
   vals={x['cost']:x for x in result if x['period']==p and x['group']==g and x['asset']=='COMBINED'};fmt=lambda mode,k:f"{vals[mode][k]:.3f}"if mode in vals else'未验证'
   text.append('|'+p+'|'+g+'|'+'|'.join([fmt(c,'return_pct')for c in ['C1','OPEN','HIGH','LOW']]+[fmt('OPEN','max_drawdown_pct')])+'|')
 text+=['',f'独立核算{len(audits)}份不重复账本，资金费按实际时刻的方向、部分退出后剩余数量逐条重新算，并核对现金/完整交易净额/期末估值及实际名义手续费。完整流水、匹配与月表随附；各模式原始逐笔完整路径重放，不是事后扣费。','', '2020仅2月16日至年底；2026仅1—10月；NOV独立区间截至11月13日08:00北京；不拼接跨年复利。官方月标记价ZIP和响应在云端保留，来源、CHECKSUM、获取时刻及SHA见mark_archive_sources.json。']
 (O/'HISTORY_REPORT.md').write_text('\n'.join(text)+'\n');print('REPORT',len(result),'rows',len(audits),'audits')
if __name__=='__main__':main()
