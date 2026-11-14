from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,csv
import numpy as np
OUT=Path(__file__).resolve().parent;TZ=timezone(timedelta(hours=8));rows=[];monthly=[]
for year in (2019,2020,2024,2025):
 folder=OUT/str(year);files=[folder/a/'DYNAMIC_result.json' for a in ('BTC','ETH')]
 complete=all(f.exists() for f in files) and all((folder/a/'status.json').exists() and json.loads((folder/a/'status.json').read_text()).get('completed') for a in ('BTC','ETH'))
 q=dict(year=year,source_market='BINANCE_SPOT_ONLY',financial_model='synthetic3x long/short; not actual spot account return',status='COMPLETE' if complete else 'PENDING')
 if complete:
  qs=[json.loads(f.read_text()) for f in files];marks=sum(np.load(folder/a/'DYNAMIC_equity.npy') for a in ('BTC','ETH'));eq=np.r_[1000.,marks]
  q.update(return_pct=100*(sum(v['ending_equity'] for v in qs)/1000-1),max_drawdown_pct=float(np.max(100*(1-eq/np.maximum.accumulate(eq)))),BTC_return_pct=qs[0]['return_pct'],ETH_return_pct=qs[1]['return_pct'],opens=sum(v['opens'] for v in qs))
  start=int(datetime(year,1,1,tzinfo=TZ).timestamp())
  for m in range(1,13):
   first=int(datetime(year,m,1,tzinfo=TZ).timestamp());end=int(datetime(year,m+1,1,tzinfo=TZ).timestamp()) if m<12 else int(datetime(year+1,1,1,tzinfo=TZ).timestamp())
   i=(first-start)//60;j=(end-start)//60;initial=1000. if i==0 else float(marks[i-1]);monthly.append(dict(year=year,month=m,return_pct=100*(float(marks[j-1])/initial-1)))
 else:
  fails=[folder/a/'failure.json' for a in ('BTC','ETH')]
  if any(f.exists() for f in fails):q.update(status='UNVERIFIED',reason='; '.join(json.loads(f.read_text())['error'] for f in fails if f.exists()))
 rows.append(q)
for name,rr in [('summary',rows),('monthly',monthly)]:
 (OUT/f'{name}.json').write_text(json.dumps(rr,ensure_ascii=False,indent=2));keys=list(dict.fromkeys(k for q in rr for k in q))
 with (OUT/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rr)
lines=['# 币安现货完整年份替代输入测试','','本轮仅更换行情来源，使用完整单一币安现货价格，不与永续或Gate拼接；原永续结果保持不变。**收益为现货行情驱动的3倍多空合成模拟，不是现货账户或Gate永续的真实可实现收益。**没有建模借币可得性、借币利息、资金费、队列或深度。','', '同一动态规则：1%固定减初始数量25%；之后每根已收盘15分钟，旧六线相对3根前方向或MACD柱首次不同向再减25%；余仓原阶梯止损。原旧六线＋ER基础入场、0.25%密集阈值、2%绝对支撑阻力距离不变。手续费0、名义3倍、每年每币500USDT独立起算。五秒相位2秒、下一笔实际成交价及原0.02%不利出场滑点不变。','', '|年份|模拟组合收益|最大回撤（分钟收盘）|BTC模拟收益|ETH模拟收益|开仓|','|---|---:|---:|---:|---:|---:|']
for q in rows:
 if q['status']=='COMPLETE':lines.append(f"|{q['year']}|{q['return_pct']:+.2f}%|{q['max_drawdown_pct']:.2f}%|{q['BTC_return_pct']:+.2f}%|{q['ETH_return_pct']:+.2f}%|{q['opens']}|")
 else:lines.append(f"|{q['year']}|{'未验证' if q['status']=='UNVERIFIED' else '运行中/待执行'}|—|—|—|{q.get('reason','')}|")
lines+=['', '数据：https://data.binance.vision/data/spot/，月度原生15分钟/1分钟K线、执行涉及日期的真实aggTrades或原始trades。所有下载验证官方SHA256，按每档案时间戳量级区分毫秒/微秒。信号与执行全取现货，原生K线缺行时，仅以官方校验通过且成交ID完整连续的同平台逐笔重建OHLCV；无成交时段须有逐笔和必要的相邻日ID连续性证据，才用上一笔已观察收盘生成零成交K线，价格不取未来值。逐项证据存*_gap_proofs.json。不能证明的缺失仍中止；不用OHLC极值顺序回退。各年各币来源、哈希和失败记录保留。',
 '', '2020 BTC额外恢复：月档案的10月27日K线与官方日档案不同；用整日原始逐笔检验日级1分钟和15分钟K线全部价格范围通过后，替换该日两周期K线并完整重跑BTC全年。原数组、CSV另存.before_daily_fix，来源、变化根数和整日逐笔检验记录在2020/BTC/daily_repair.json。没有修改任何成交价格或策略参数。', '', 'Gate访问检查见gate_access.json：旧K线API拒绝超期范围，2019所查逐笔档案404，2024/2025逐笔档案可访问。本次选择用户同时授权的现货完整输入方案，没有声称Gate逐笔不可访问。',
 '', '命令：','```sh','/workspace/.venv-btc-eth-original/bin/python -u outputs/er_dynamic_spot_fallback/supervisor.py > outputs/er_dynamic_spot_fallback/supervisor.log 2>&1','/workspace/.venv-btc-eth-original/bin/python outputs/er_dynamic_spot_fallback/collect.py','```','2020修复及重跑命令：`python repair_2020_daily.py`，`python worker.py 2020 BTC > 2020/BTC/repaired_retry.log 2>&1`（均位于本目录，使用相同虚拟环境）。', '调度器最多3个独立进程，逐项调用`python worker.py YEAR BTC|ETH`。每币run.log为实际输出。2019两币首次因原生K线缺行停止，随后以同平台完整逐笔核对并重建后重试，命令为`python worker.py 2019 BTC|ETH`，输出保留在各币retry.log。没有参数寻优，没有覆盖原版。']
(OUT/'report.md').write_text('\n'.join(lines)+'\n');print(json.dumps(rows,ensure_ascii=False))
