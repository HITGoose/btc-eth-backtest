from pathlib import Path
from datetime import datetime
import sys,json,csv
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_2020 as driver
out=driver.OUT;e=driver.e;summary=[];monthly=[]
for asset in ('BTC','ETH'):
 assert json.loads((out/asset/'status.json').read_text())['completed']
for profile in ('CONTROL','PARTIAL'):
 qs=[json.loads((out/a/f'{profile}_result.json').read_text()) for a in ('BTC','ETH')]
 marks=sum(np.load(out/a/f'{profile}_equity.npy') for a in ('BTC','ETH'))
 eq=np.r_[1000.,marks];dd=float(np.max(100*(1-eq/np.maximum.accumulate(eq))))
 summary.append(dict(profile=profile,period_beijing=qs[0]['period_beijing'],full_year_2020=False,
   return_pct=100*(sum(q['ending_equity'] for q in qs)/1000-1),max_drawdown_pct=dd,
   BTC_return_pct=qs[0]['return_pct'],ETH_return_pct=qs[1]['return_pct'],
   opens=sum(q['opens'] for q in qs),partial_exits=sum(q['stats'].get('partial_exits',0) for q in qs)))
 for month in range(2,13):
  first=max(driver.START,int(datetime(2020,month,1,tzinfo=e.r.TZ).timestamp()))
  end=int(datetime(2020,month+1,1,tzinfo=e.r.TZ).timestamp()) if month<12 else driver.END
  left=(first-driver.START)//60;right=(end-driver.START)//60
  start_equity=float(marks[left-1]) if left else 1000.;final=float(marks[right-1])
  monthly.append(dict(month=f'2020-{month:02}',profile=profile,partial_month=month==2,
     return_pct=100*(final/start_equity-1)))
for name,rows in [('summary',summary),('monthly',monthly)]:
 (out/f'{name}.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
 fields=list(dict.fromkeys(k for q in rows for k in q))
 with (out/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
lines=['# 2020可用窗口：ER固定分批止盈对照','',
 '**2020全年收益未验证。实际测试仅为北京时间2020-02-16 00:00至2021-01-01 00:00，不是2020全年。缺失1月1日至2月15日交易窗口，未做年化外推。**','',
 '原2019预热月档案及抽查日档案404；币安公开FAPI451；Gate公开K线API400（超出历史可取范围）。实际HTTP证据见access_check.json；2019月档案证据见../other_years_050/prehistory_access.json。',
 '以2020年1月2日起的原生15分钟数据预热45天，随后从2月16日起交易。两币预热网格、价格字段与完整交易窗口均检查通过。此可用窗口不代表2019缺失数据已补齐。','',
 '数据：币安USDT永续官方15分钟、1分钟K线及实际逐笔，官方SHA256校验。手续费0、3倍名义仓位、每币500USDT；旧六MA（SMA/EMA20、60、120）、原ER12/120小时、0.25%密集阈值、2%支撑阻力绝对距离和过渡期暂停不变。',
 '新实验仅增加：5秒相位2秒轮询观察顺向达到2%减初始数量1/3，达到3%再减1/3，余仓按原阶梯止损。分批取下一笔实际成交价加0.02%不利滑点，数量按原步长向下取整；原止损优先。','',
 '|版本|窗口组合收益|最大回撤（分钟收盘）|BTC收益|ETH收益|开仓|',
 '|---|---:|---:|---:|---:|---:|']
for q in summary:lines.append(f"|{q['profile']}|{q['return_pct']:+.2f}%|{q['max_drawdown_pct']:.2f}%|{q['BTC_return_pct']:+.2f}%|{q['ETH_return_pct']:+.2f}%|{q['opens']}|")
lines+=['','|月份|原全仓|分批|','|---|---:|---:|']
for m in range(2,13):
 a=[q for q in monthly if q['month']==f'2020-{m:02}'];label='2月16日起' if m==2 else f'{m}月'
 lines.append(f"|{label}|{a[0]['return_pct']:+.2f}%|{a[1]['return_pct']:+.2f}%|")
lines+=['', '无OHLC高低顺序回退。原全仓与分批同时使用相同入场候选和逐笔价格。当前没有2020同窗口的已验证旧结果文件供逐笔回归，因此CONTROL是本次实际运行结果，不是此前全年汇报值。',
 '资金费、深度、排队和真实部分成交仍未模拟；逐笔触价及下一笔价格成交为执行代理。原仓库源码及2026实验文件均未修改。未因收益修改参数。','',
 '运行命令：','```sh',
 '/workspace/.venv-btc-eth-original/bin/python -u outputs/er_partial_2020/run_2020.py BTC > outputs/er_partial_2020/BTC_run.log 2>&1',
 '/workspace/.venv-btc-eth-original/bin/python -u outputs/er_partial_2020/run_2020.py ETH > outputs/er_partial_2020/ETH_run.log 2>&1',
 '/workspace/.venv-btc-eth-original/bin/python outputs/er_partial_2020/collect.py','```',
 '官方数据来源和校验值：根目录各币*_candle_sources.json及各币目录*_tick_sources.json。']
(out/'report.md').write_text('\n'.join(lines)+'\n');print(json.dumps(summary,ensure_ascii=False))
