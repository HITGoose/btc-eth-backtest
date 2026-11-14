from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,csv
import numpy as np
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent.parent;TZ=timezone(timedelta(hours=8));rows=[];monthly=[]
for year in range(2019,2027):
 folder=ROOT/f'outputs/er_dynamic_compare/{year}' if year in (2020,2026) else OUT/str(year)
 files=[folder/a/'DYNAMIC_result.json' for a in ('BTC','ETH')]
 complete=all(f.exists() for f in files) and all((folder/a/'status.json').exists() and json.loads((folder/a/'status.json').read_text()).get('completed') for a in ('BTC','ETH'))
 row=dict(year=year,status='COMPLETE' if complete else 'PENDING',period='2020-02-16 to2020-12-31' if year==2020 else '2026-01-01 to2026-10-31' if year==2026 else f'{year} calendar year',full_calendar_year=year not in (2020,2026),reused_previous_run=year in (2020,2026))
 if complete:
  qs=[json.loads(f.read_text()) for f in files];marks=sum(np.load(folder/a/'DYNAMIC_equity.npy') for a in ('BTC','ETH'));eq=np.r_[1000.,marks]
  row.update(return_pct=100*(sum(q['ending_equity'] for q in qs)/1000-1),max_drawdown_pct=float(np.max(100*(1-eq/np.maximum.accumulate(eq)))),BTC_return_pct=qs[0]['return_pct'],ETH_return_pct=qs[1]['return_pct'],opens=sum(q['opens'] for q in qs),BTC_opens=qs[0]['opens'],ETH_opens=qs[1]['opens'])
  if year==2020:start=int(datetime(year,2,16,tzinfo=TZ).timestamp());first_month=2;last_month=12
  else:start=int(datetime(year,1,1,tzinfo=TZ).timestamp());first_month=1;last_month=10 if year==2026 else 12
  for m in range(first_month,last_month+1):
   first=max(start,int(datetime(year,m,1,tzinfo=TZ).timestamp()));end=int(datetime(year,m+1,1,tzinfo=TZ).timestamp()) if m<12 else int(datetime(year+1,1,1,tzinfo=TZ).timestamp())
   i=(first-start)//60;j=(end-start)//60;initial=1000. if i==0 else float(marks[i-1]);final=float(marks[j-1])
   monthly.append(dict(year=year,month=m,return_pct=100*(final/initial-1),partial_month=year==2020 and m==2))
 else:
  errors=[folder/a/'failure.json' for a in ('BTC','ETH')]
  if any(p.exists() for p in errors):row.update(status='UNVERIFIED',reason='; '.join(json.loads(p.read_text())['error'] for p in errors if p.exists()))
 rows.append(row)
for name,rr in [('summary',rows),('monthly',monthly)]:
 (OUT/f'{name}.json').write_text(json.dumps(rr,ensure_ascii=False,indent=2));fields=list(dict.fromkeys(k for q in rr for k in q))
 with (OUT/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rr)
asset_rows=[]
for year in range(2019,2027):
 folder=ROOT/f'outputs/er_dynamic_compare/{year}' if year in (2020,2026) else OUT/str(year)
 for asset in ('BTC','ETH'):
  f=folder/asset/'DYNAMIC_result.json';status=folder/asset/'status.json'
  if f.exists() and status.exists() and json.loads(status.read_text()).get('completed'):
   q=json.loads(f.read_text());asset_rows.append(dict(year=year,asset=asset,return_pct=q['return_pct'],opens=q['opens']))
(OUT/'asset_results.json').write_text(json.dumps(asset_rows,ensure_ascii=False,indent=2))
lines=['# 2019—2026旧ER动态减仓年度扩展','','动态规则固定：顺向1%按五秒相位2秒轮询触发，平初始数量25%；实际执行第一档后，每根已完成15分钟K线检查旧六线各自相对3根前是否严格同向、MACD柱是否同向，首次任一不满足再平初始数量25%，每笔仅一次。余仓沿用原阶梯止损，止损优先。减仓取请求后首笔实际成交价加原0.02%不利滑点，数量向下取原步长。','', '旧六线为SMA/EMA20、60、120；原ER12/120小时、0.25%密集阈值、2%支撑阻力绝对距离、BASELINE基础入场和过渡期暂停均不变。手续费0、3倍名义仓位，每年BTC与ETH分别500USDT，合计1000USDT独立起算；本表不是跨年连续复利。没有按年份调参或自动搜索。','', '**2020仅2月16日至年底；2026仅1—10月。这两行不是全年，直接复用此前同规则实测结果。**','', '|年份|窗口组合收益|最大回撤（分钟收盘权益）|BTC收益|ETH收益|开仓|范围/状态|','|---|---:|---:|---:|---:|---:|---|']
for q in rows:
 if q['status']=='COMPLETE':lines.append(f"|{q['year']}|{q['return_pct']:+.2f}%|{q['max_drawdown_pct']:.2f}%|{q['BTC_return_pct']:+.2f}%|{q['ETH_return_pct']:+.2f}%|{q['opens']}|{q['period']}|")
 else:lines.append(f"|{q['year']}|{'未验证' if q['status']=='UNVERIFIED' else '运行中/待执行'}|—|—|—|—|{q.get('reason','未完成')}|")
lines+=['','2019：实际请求官方所需预热档案，缺失时记录HTTP错误；不混入现货或其他平台价格。2024：重新下载并校验2024-10-28官方aggTrades及原始trades，先检查与原生分钟K线一致性；不通过则中止数据预检，不把它称为完整动态回测。每币错误、样本、URL及SHA256保存在对应年份目录。',
 '', '来源为币安USDT永续官方原生15分钟、1分钟及实际逐笔，逐笔官方SHA256匹配，禁止OHLC顺序假设回退。复用原生K线：../other_years_050/YYYY/data，来源清单在其各年目录。逐笔价格用于执行，不验证真实订单深度、排队或部分成交；资金费沿用未计。动态规则是新实验，不能据收益判定已复刻参考机器人。',
 '', '2025若某币在原版未触及的交易日发生新的档案冲突，按该年各币failure.json及daily_kline_diagnostic.json记录停止原因；一币完成不冒充组合完成。各币已完成收益另存asset_results.json。', '', '命令：','```sh','/workspace/.venv-btc-eth-original/bin/python -u outputs/er_dynamic_annual_2019_2026/supervisor.py > outputs/er_dynamic_annual_2019_2026/supervisor.log 2>&1','/workspace/.venv-btc-eth-original/bin/python outputs/er_dynamic_annual_2019_2026/collect.py','```',
 '调度器最多4个独立Python进程，仅运行DYNAMIC账本。逐项命令：`python worker.py YEAR BTC|ETH`，各年各币run.log保留真实输出；已有completed=true的结果不会重跑。']
(OUT/'report.md').write_text('\n'.join(lines)+'\n');print(json.dumps(rows,ensure_ascii=False))
