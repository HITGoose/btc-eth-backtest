from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,csv
import numpy as np
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent.parent;TZ=timezone(timedelta(hours=8));rows=[];annual=[]
for y in range(2016,2027):
 market='未取得完整逐笔来源' if y==2016 else '币安现货价格模拟（仅11—12月）' if y==2017 else '币安现货价格模拟' if y in (2018,2019,2020,2024,2025) else '币安USDT永续'
 for profile in ('CONTROL','DYNAMIC'):
  if y==2026:folder=ROOT/('outputs/er_partial_2026' if profile=='CONTROL' else 'outputs/er_dynamic_compare/2026')
  elif profile!='DYNAMIC' or y<=2018:folder=OUT/str(y)
  elif y in (2019,2020,2024,2025):folder=ROOT/f'outputs/er_dynamic_spot_fallback/{y}'
  else:folder=ROOT/f'outputs/er_dynamic_annual_2019_2026/{y}'
  paths=[folder/a/f'{profile}_result.json' for a in ('BTC','ETH')]
  complete=all(f.exists() for f in paths) and all((folder/a/'status.json').exists() and json.loads((folder/a/'status.json').read_text()).get('completed') for a in ('BTC','ETH'))
  status='COMPLETE' if complete else 'UNVERIFIED' if any((OUT/str(y)/a/'failure.json').exists() for a in ('BTC','ETH')) else 'PENDING'
  if y==2026 and complete:status='COMPLETE_THROUGH_OCTOBER'
  if complete:
   qs=[json.loads(f.read_text()) for f in paths];marks=sum(np.load(folder/a/f'{profile}_equity.npy') for a in ('BTC','ETH'));eq=np.r_[1000.,marks]
   annual.append(dict(year=y,profile=profile,market=market,coverage='November-December only' if y==2017 else 'January-October only' if y==2026 else 'full year',return_pct=100*(sum(q['ending_equity'] for q in qs)/1000-1),max_drawdown_pct=float(np.max(100*(1-eq/np.maximum.accumulate(eq))))))
  start=int(datetime(y,11 if y==2017 else 1,1,tzinfo=TZ).timestamp())
  for m in range(1,13):
   q=dict(year=y,month=m,profile=profile,market=market,status=status,return_pct=None)
   if y==2017 and m<11:q['status']='UNVERIFIED'
   elif y==2026 and m>=11:q['status']='NOT_TESTED'
   elif complete:
    first=int(datetime(y,m,1,tzinfo=TZ).timestamp());end=int(datetime(y,m+1,1,tzinfo=TZ).timestamp()) if m<12 else int(datetime(y+1,1,1,tzinfo=TZ).timestamp());i=(first-start)//60;j=(end-start)//60
    initial=1000. if i==0 else float(marks[i-1]);q['return_pct']=100*(float(marks[j-1])/initial-1)
   rows.append(q)
for name,rr in [('monthly_long',rows),('annual',annual)]:
 (OUT/f'{name}.json').write_text(json.dumps(rr,ensure_ascii=False,indent=2));fields=list(dict.fromkeys(k for q in rr for k in q))
 with (OUT/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rr)
wide=[];index={(q['year'],q['month'],q['profile']):q for q in rows}
for y in range(2016,2027):
 for m in range(1,13):
  row=dict(year=y,month=m,market=index[y,m,'CONTROL']['market'])
  for p in ('CONTROL','DYNAMIC'):row[p]=index[y,m,p]['return_pct'];row[p+'_status']=index[y,m,p]['status']
  wide.append(row)
with (OUT/'monthly_comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(wide[0]));w.writeheader();w.writerows(wide)
lines=['# 2016—2026每月动态与原ER对照','','CONTROL：原全仓阶梯止损退出。DYNAMIC：顺向1%减25%，之后已收盘15分钟六线方向或MACD首次减弱再减25%，余仓原阶梯止损。','', '旧六线SMA/EMA20、60、120＋原ER基础入场不变；手续费0、3倍、每年每币500USDT重置，月收益按月初总权益计算并含浮盈亏。年收益不能把月收益直接相加。每个年份两版使用同一市场、同一窗口。市场跨年不同，因此不能视为统一市场的连续收益。现货为价格驱动的合成多空，未计借币利息。',
 '', '已测动态及2026两版本直接读取实际结果，不重复财务回放。用户确认保持逐笔口径：2016全年和2017前10个月缺完整同口径逐笔则标未验证，2017只补测11—12月，绝不生成OHLC高低先后假设收益；2026仅1—10月，11、12月未测。','']
for y in range(2016,2027):
 lines+= [f'## {y}（{index[y,1,"CONTROL"]["market"]}）','','|月份|原ER全仓|动态|','|---|---:|---:|']
 for m in range(1,13):
  vals=[]
  for p in ('CONTROL','DYNAMIC'):
   q=index[y,m,p];vals.append(f"{q['return_pct']:+.2f}%" if q['return_pct'] is not None else '未测试' if q['status']=='NOT_TESTED' else '未验证' if q['status']=='UNVERIFIED' else '运行中')
  lines.append('|'+str(m)+'月|'+'|'.join(vals)+'|')
 lines.append('')
lines+=['数据来源及恢复证据沿用各年度已校验输入。原ER全仓版新增回放所用逐笔URL及官方SHA256见对应年币种目录*_tick_sources.json；2018及更早新增现货源证据见spot_inputs目录。旧原始代码、旧输出不覆盖。','', '用户已取消固定版对比，已停止旧配对任务，后续仅运行CONTROL与DYNAMIC；固定版不进入任何月表。2016—2017另查Bitfinex公开逐笔接口403、Bitcoincharts档案503，证据见early_alternative_access.json。当前未获取完整同口径逐笔，2016各月及2017前10个月未验证；2017年底两个月另用完整现货逐笔补测，不视作全年。2018不规则K线整日用完整逐笔重建，月/日差异以整日原始逐笔验证日档案后恢复，证据保留在spot_inputs与年币种目录。', '', '命令：','```sh','/workspace/.venv-btc-eth-original/bin/python -u outputs/monthly_three_versions_2016_2026/supervisor.py > outputs/monthly_three_versions_2016_2026/two_version_supervisor.log 2>&1','/workspace/.venv-btc-eth-original/bin/python outputs/monthly_three_versions_2016_2026/collect.py','```']
(OUT/'report.md').write_text('\n'.join(lines)+'\n');print('Updated monthly rows:',len(wide))
