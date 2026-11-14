from pathlib import Path
from datetime import datetime
import sys,json,csv,calendar
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run as e
out=e.OUT;summary=[];monthly=[];partials=[]
for asset in ('BTC','ETH'):
 status=out/asset/'status.json'
 if not status.exists() or not json.loads(status.read_text()).get('completed'):
  raise RuntimeError('Incomplete actual replay: '+asset)
 for profile in ('CONTROL','PARTIAL'):
  q=json.loads((out/asset/f'{profile}_result.json').read_text())
  for event in q['events']:
   if event['event']=='partial_exit':partials.append(dict(asset=asset,profile=profile,time_beijing=e.r.local_us(event['time_us']),**event))
for profile in ('CONTROL','PARTIAL'):
 qs=[json.loads((out/a/f'{profile}_result.json').read_text()) for a in ('BTC','ETH')]
 marks=sum(np.load(out/a/f'{profile}_equity.npy') for a in ('BTC','ETH'))
 values=np.r_[1000.,marks];dd=float(np.max(100*(1-values/np.maximum.accumulate(values))))
 summary.append(dict(profile=profile,return_pct=100*(sum(q['ending_equity'] for q in qs)/1000-1),
  max_drawdown_pct=dd,BTC_return_pct=qs[0]['return_pct'],ETH_return_pct=qs[1]['return_pct'],
  opens=sum(q['opens'] for q in qs),partial_exit_count=sum(q['stats'].get('partial_exits',0) for q in qs),
  ending_equity=sum(q['ending_equity'] for q in qs)))
 for month in range(1,11):
  first=int(datetime(2026,month,1,tzinfo=e.r.TZ).timestamp())
  end=int(datetime(2026,month+1,1,tzinfo=e.r.TZ).timestamp())
  left=(first-e.d.START)//60;right=(end-e.d.START)//60
  initial=1000. if left==0 else float(marks[left-1]);final=float(marks[right-1])
  monthly.append(dict(month=f'2026-{month:02}',profile=profile,return_pct=100*(final/initial-1),
    initial_equity=initial,ending_equity=final))
for name,rows in [('summary',summary),('monthly',monthly),('partial_fills',partials)]:
 e.d.dump(out/f'{name}.json',rows)
 fields=list(dict.fromkeys(k for row in rows for k in row))
 with (out/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
lines=['# 旧ER基础版：固定分批止盈实验','',
 '期间：2026年1月1日至10月31日，北京时间。币安USDT永续官方原生15分钟、1分钟K线和实际逐笔成交。BTC、ETH各500USDT、3倍名义仓位、手续费0、原0.02%出场不利滑点。',
 '旧六线SMA/EMA20、60、120，ER12小时/120小时、密集阈值0.25%、2%支撑阻力绝对距离、过渡期暂停、基础版入场均保持不变。没有采用新六MA或双穿越。','',
 '用户确认的独立实验：5秒相位2秒轮询观察顺向达到2%时请求平初始数量1/3，达到3%再请求平1/3，余仓沿用原阶梯止损。数量向下取步长，余量保留到最终止损；跳过两档时两批一并请求。分批按请求后首笔实际成交价加不利滑点模拟成交，止损优先；不假定目标价成交。','',
 '|版本|组合收益|最大回撤（分钟收盘权益）|BTC收益|ETH收益|开仓|分批成交|',
 '|---|---:|---:|---:|---:|---:|---:|']
for q in summary:lines.append(f"|{q['profile']}|{q['return_pct']:+.2f}%|{q['max_drawdown_pct']:.2f}%|{q['BTC_return_pct']:+.2f}%|{q['ETH_return_pct']:+.2f}%|{q['opens']}|{q['partial_exit_count']}|")
lines+=['','## 月收益（连续账户，含浮盈亏）','','|月份|原全仓退出|固定分批退出|','|---|---:|---:|']
for m in range(1,11):
 a=[v for v in monthly if v['month']==f'2026-{m:02}']
 lines.append(f"|2026-{m:02}|{a[0]['return_pct']:+.2f}%|{a[1]['return_pct']:+.2f}%|")
lines+=['','原全仓对照的每笔交易时间、方向、价格、数量、盈亏、档位和期末权益均与此前已验证ER结果一致。分批版本逐笔、资金账本与数量守恒检查通过；合成测试不充当历史证据。',
 '保留原work/源码及原实验输出，新规则仅在本目录生效。回测仍未模拟真实排队、部分成交、市场深度及资金费；分批市价退出为下一笔成交价代理，真实可成交数量未验证。',
 '这是一组用户确认的固定实验，没有参数搜索；仅完成2026年1—10月，其他年份分批收益未验证，不能据此认定更接近参考机器人。','',
 '命令：','```sh',
 '/workspace/.venv-btc-eth-original/bin/python outputs/er_partial_2026/test_engine.py',
 '/workspace/.venv-btc-eth-original/bin/python -u outputs/er_partial_2026/run.py BTC > outputs/er_partial_2026/BTC_run.log 2>&1',
 '/workspace/.venv-btc-eth-original/bin/python -u outputs/er_partial_2026/run.py ETH > outputs/er_partial_2026/ETH_run.log 2>&1',
 '/workspace/.venv-btc-eth-original/bin/python outputs/er_partial_2026/collect.py','```',
 '来源：各币目录下`*_tick_sources.json`保存实际访问的官方URL和SHA256；原生K线来源见`../attribution_2026/candle_sources.json`。']
(out/'report.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(summary,ensure_ascii=False))
