from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,csv
import numpy as np
OUT=Path(__file__).resolve().parent;TZ=timezone(timedelta(hours=8));rows=[];monthly=[]
for year in (2024,2025):
 folder=OUT/str(year)
 for profile in ('CONTROL','DYNAMIC'):
  files=[folder/a/f'{profile}_result.json' for a in ('BTC','ETH')]
  complete=all(f.exists() for f in files) and all((folder/a/'status.json').exists() and json.loads((folder/a/'status.json').read_text()).get('completed') for a in ('BTC','ETH'))
  q=dict(year=year,profile=profile,market='BINANCE_USDT_PERPETUAL_ONLY',status='COMPLETE' if complete else 'PENDING')
  if complete:
   qq=[json.loads(f.read_text()) for f in files];marks=sum(np.load(folder/a/f'{profile}_equity.npy') for a in ('BTC','ETH'));v=np.r_[1000.,marks]
   q.update(return_pct=100*(sum(z['ending_equity'] for z in qq)/1000-1),max_drawdown_pct=float(np.max(100*(1-v/np.maximum.accumulate(v)))),BTC_return_pct=qq[0]['return_pct'],ETH_return_pct=qq[1]['return_pct'],opens=sum(z['opens'] for z in qq),disagreement_days_by_asset={a:qq[i]['disagreement_days'] for i,a in enumerate(('BTC','ETH'))})
   start=int(datetime(year,1,1,tzinfo=TZ).timestamp())
   for m in range(1,13):
    begin=int(datetime(year,m,1,tzinfo=TZ).timestamp());end=int(datetime(year,m+1,1,tzinfo=TZ).timestamp()) if m<12 else int(datetime(year+1,1,1,tzinfo=TZ).timestamp());i=(begin-start)//60;j=(end-start)//60;initial=1000. if i==0 else float(marks[i-1]);monthly.append(dict(year=year,month=m,profile=profile,return_pct=100*(float(marks[j-1])/initial-1)))
  else:
   errors=[folder/a/'failure.json' for a in ('BTC','ETH')]
   if any(f.exists() for f in errors):q.update(status='UNVERIFIED',reason='; '.join(json.loads(f.read_text())['error'] for f in errors if f.exists()))
  rows.append(q)
for name,rr in [('annual',rows),('monthly',monthly)]:
 (OUT/f'{name}.json').write_text(json.dumps(rr,ensure_ascii=False,indent=2));fields=list(dict.fromkeys(k for q in rr for k in q))
 with (OUT/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rr)
lines=['# 币安USDT永续：2024/2025官方逐笔执行补测','','只使用币安USDT永续。原生已收盘15分钟K线用于原ER入场及动态减仓判断；官方原始逐笔用于限价触达、止损、减仓、轮询最新价及持仓估值。没有现货或Gate输入，也未修改任何成交价格。','', '手续费0、名义3倍，每年每币500USDT独立起算；原0.02%出场不利滑点、2%支撑阻力绝对距离、旧六线SMA/EMA20/60/120和原ER规则保持不变。CONTROL为原全仓阶梯止损，DYNAMIC为顺向1%减25%、之后首根已完成15分钟趋势减弱再减25%，余仓原阶梯止损。固定版不运行。','', '|年份|版本|组合收益|最大回撤（分钟实际逐笔收盘估值）|BTC收益|ETH收益|开仓|','|---|---|---:|---:|---:|---:|---:|']
for q in rows:
 if q['status']=='COMPLETE':lines.append(f"|{q['year']}|{q['profile']}|{q['return_pct']:+.2f}%|{q['max_drawdown_pct']:.2f}%|{q['BTC_return_pct']:+.2f}%|{q['ETH_return_pct']:+.2f}%|{q['opens']}|")
 else:lines.append(f"|{q['year']}|{q['profile']}|{'未验证' if q['status']=='UNVERIFIED' else '运行中'}|—|—|—|{q.get('reason','')}|")
lines+=['','## 月收益','','|月份|原ER|动态|','|---|---:|---:|']
for y in (2024,2025):
 for m in range(1,13):
  values=[next((q['return_pct'] for q in monthly if q['year']==y and q['month']==m and q['profile']==p),None) for p in ('CONTROL','DYNAMIC')]
  fmt=lambda v:'未完成' if v is None else f'{v:+.2f}%';lines.append(f'|{y}-{m:02}|{fmt(values[0])}|{fmt(values[1])}|')
lines+=['','## 执行差异与数据记录','','此前遇到K线/逐笔高低价不一致就停止；本次按照用户要求使用币安档案，保留不一致记录但不删除逐笔。不再依赖K线高低价裁剪持仓或挂单分钟；所有活动分钟都会读取实际原始逐笔，轮询价从完整逐笔取得，持仓估值也取实际逐笔。入场仍按币安提供的已收盘K线，不因逐笔差异重建或调整信号K线。',
 '为避免Python逐笔遍历耗时，按当前持仓/挂单阈值向量寻找最早会改变状态的真实成交，完整保留轮询、提交/到期边界及减仓后首笔成交。每次事件处理后重新寻找，不能预先批量生成事件；64组合成案例已与每笔逐条处理的成交、事件、资金和分钟权益逐项一致。合成验证不冒充历史验证。',
 '官方SHA256、原始成交ID严格递增、时间单位和日期范围均检查。官方档案中存在ID跳号，跳号本身不足以证明缺失市场成交，按档案提供的记录回放并记录跳号数，不补造缺号交易；市场真实逐笔全集的完整性没有独立证明。文件缺失、重复ID、非正价格等仍会失败；只是不再把K线包络差异直接视为逐笔无效。各币raw_sources.json保存官方URL及哈希，candle_tick_disagreements.json保存不一致日和实际样本。估值口径改为逐笔，旧版结果不覆盖。',
 '限价成交仍为全额触价代理，排队、深度和实际部分成交未模拟；资金费沿用未计。原+10秒提交边界行为保留。','', '命令：','```sh','/workspace/.venv-btc-eth-original/bin/python outputs/binance_perpetual_raw_execution/test_engine.py','/workspace/.venv-btc-eth-original/bin/python -u outputs/binance_perpetual_raw_execution/supervisor.py > outputs/binance_perpetual_raw_execution/supervisor.log 2>&1','/workspace/.venv-btc-eth-original/bin/python outputs/binance_perpetual_raw_execution/collect.py','```']
prior=Path(__file__).resolve().parents[1]/'binance_perpetual_only'/'annual.json'
merged=json.loads(prior.read_text())
for row in merged:
 row['execution_version']='previous verified replay'
 if row['year'] in (2024,2025):
  pair=[q for q in rows if q['year']==row['year']]
  if all(q['status']=='COMPLETE' for q in pair):
   row.update(ER_return_pct=next(q['return_pct'] for q in pair if q['profile']=='CONTROL'),dynamic_return_pct=next(q['return_pct'] for q in pair if q['profile']=='DYNAMIC'),status='已实测全年',reason='',execution_version='official raw prints, every active minute')
(OUT/'perpetual_only_annual.json').write_text(json.dumps(merged,ensure_ascii=False,indent=2))
fields=list(dict.fromkeys(k for q in merged for k in q))
with (OUT/'perpetual_only_annual.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(merged)
lines+=['', '## 仅永续：已完成区间汇总', '', '此前已验证的2020部分年度、2021—2023和2026年1—10月直接复用，没有重跑；2024、2025使用本次原始逐笔全活动分钟执行版本，估值也改用实际逐笔。均为币安USDT永续，不含现货。', '', '|年份|范围|原ER|动态|', '|---|---|---:|---:|']
for q in merged:
 if q['year']<2019:continue
 fmt=lambda v:'未验证' if v is None else f'{v:+.2f}%'
 lines.append(f"|{q['year']}|{q['period']}|{fmt(q['ER_return_pct'])}|{fmt(q['dynamic_return_pct'])}|")
(OUT/'report.md').write_text('\n'.join(lines)+'\n');print(json.dumps(rows,ensure_ascii=False))
