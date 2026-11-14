from pathlib import Path
from datetime import datetime
import json,csv,sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent));import dynamic as x
OUT=x.OUT;rows=[];months=[]
for year in (2020,2026):
 old=OUT.parent/f'er_partial_{year}'
 sources={'CONTROL':old,'EARLY_2':OUT.parent/'er_partial_variants_2020' if year==2020 else OUT/str(year),'DYNAMIC':OUT/str(year)}
 start=x.v.driver.START if year==2020 else int(datetime(2026,1,1,tzinfo=x.r.TZ).timestamp())
 end=x.v.driver.END if year==2020 else int(datetime(2026,11,1,tzinfo=x.r.TZ).timestamp())
 for name,folder in sources.items():
  qs=[json.loads((folder/a/f'{name}_result.json').read_text()) for a in ('BTC','ETH')]
  for a in ('BTC','ETH'):
   if folder==OUT/str(year):assert json.loads((folder/a/'status.json').read_text())['completed']
  marks=sum(np.load(folder/a/f'{name}_equity.npy') for a in ('BTC','ETH'));assert len(marks)==(end-start)//60
  eq=np.r_[1000.,marks];rows.append(dict(year=year,profile=name,window=[x.r.local_s(start),x.r.local_s(end)],return_pct=100*(sum(q['ending_equity'] for q in qs)/1000-1),max_drawdown_pct=float(np.max(100*(1-eq/np.maximum.accumulate(eq)))),BTC_return_pct=qs[0]['return_pct'],ETH_return_pct=qs[1]['return_pct'],opens=sum(q['opens'] for q in qs),new_replay=folder==OUT/str(year)))
  for m in range(2 if year==2020 else 1,13 if year==2020 else 11):
   left=max(start,int(datetime(year,m,1,tzinfo=x.r.TZ).timestamp()))
   right=int(datetime(year,m+1,1,tzinfo=x.r.TZ).timestamp()) if m<12 else end
   i=(left-start)//60;j=(right-start)//60;initial=1000 if i==0 else float(marks[i-1])
   months.append(dict(year=year,month=m,profile=name,return_pct=100*(float(marks[j-1])/initial-1),partial_month=year==2020 and m==2))
for file,rr in [('summary',rows),('monthly',months)]:
 (OUT/f'{file}.json').write_text(json.dumps(rr,ensure_ascii=False,indent=2));fields=list(dict.fromkeys(k for q in rr for k in q))
 with (OUT/f'{file}.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rr)
labels={'CONTROL':'原全仓退出','EARLY_2':'固定1%、2%各减25%','DYNAMIC':'1%减25%＋趋势减弱再减25%'}
lines=['# 旧ER：固定与动态减仓对照','','2020实际窗口：2月16日至12月31日，非全年，年初缺2019预热数据。2026实际窗口：1月1日至10月31日，非全年。不同年份窗口不作全年等长比较。','', '沿用旧六线SMA/EMA20、60、120和ER12/120小时基础版；0.25%密集阈值、2%绝对支撑阻力距离、过渡期暂停及其他入场不变。每币500USDT，3倍名义仓位，手续费0、原出场不利滑点0.02%、五秒相位2秒轮询。','', '动态规则：顺向达到1%固定减初始数量25%，以随后首笔真实成交价模拟成交；第一档实际执行后，每根15分钟收盘比较六条旧均线各自与3根前方向和MACD柱符号。六线仍严格同向且MACD同向则持有，任一首次不满足就再请求减初始数量25%，以随后首笔成交价模拟执行，每笔仅一次；余仓按原阶梯止损。止损优先，不能向不利方向移动。没有把ER变化另加为出场条件。','', '这是用户确认的新实验规则，不代表参考机器人原规则。按原数量步长向下取整。原全仓对照和2020固定两档结果直接读取以前实际结果；仅新增2020动态、2026动态和2026固定两档回放。','', '|窗口年份|方案|组合收益|最大回撤（分钟收盘）|BTC收益|ETH收益|开仓|','|---|---|---:|---:|---:|---:|---:|']
for q in rows:lines.append(f"|{q['year']}|{labels[q['profile']]}|{q['return_pct']:+.2f}%|{q['max_drawdown_pct']:.2f}%|{q['BTC_return_pct']:+.2f}%|{q['ETH_return_pct']:+.2f}%|{q['opens']}|")
lines+=['','数据：币安USDT永续官方原生15分钟、1分钟K线与实际逐笔成交，SHA256校验；来源URL及哈希保留在各年各币目录*_tick_sources.json，原生K线沿用../er_partial_2020/*_candle_sources.json及../attribution_2026/candle_sources.json。禁止OHLC回退。','', '动态信号只读取请求时刻已经收盘的15分钟K线；合成测试覆盖首次减仓前不激活动态、趋势保持不退出、未收盘不读取、首次减弱仅一次及多空资金守恒。历史运行逐笔资金与数量守恒检查通过。资金费、深度、排队与真实部分成交沿用未模拟限制；下一笔成交价为执行代理。没有自动参数搜索，没有修改原策略文件。','', '执行命令：','```sh']
for y in (2020,2026):
 for a in ('BTC','ETH'):lines.append(f'/workspace/.venv-btc-eth-original/bin/python -u outputs/er_dynamic_compare/dynamic.py {y} {a} > outputs/er_dynamic_compare/{y}_{a}.log 2>&1')
lines+=['/workspace/.venv-btc-eth-original/bin/python outputs/er_dynamic_compare/collect.py','```']
(OUT/'report.md').write_text('\n'.join(lines)+'\n');print(json.dumps(rows,ensure_ascii=False))
