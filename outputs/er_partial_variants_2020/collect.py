from pathlib import Path
import json,csv
import numpy as np
OUT=Path(__file__).resolve().parent;OLD=OUT.parent/'er_partial_2020'
rows=json.loads((OLD/'summary.json').read_text())
for row in rows:row['source']='previous actual run, not rerun'
for name in ('EARLY_2','THREE_3','LATE_2'):
 qs=[json.loads((OUT/a/f'{name}_result.json').read_text()) for a in ('BTC','ETH')]
 for a in ('BTC','ETH'):assert json.loads((OUT/a/'status.json').read_text())['completed']
 marks=sum(np.load(OUT/a/f'{name}_equity.npy') for a in ('BTC','ETH'));eq=np.r_[1000.,marks]
 rows.append(dict(profile=name,return_pct=100*(sum(q['ending_equity'] for q in qs)/1000-1),max_drawdown_pct=float(np.max(100*(1-eq/np.maximum.accumulate(eq)))),BTC_return_pct=qs[0]['return_pct'],ETH_return_pct=qs[1]['return_pct'],opens=sum(q['opens'] for q in qs),source='new actual tick replay'))
(OUT/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
keys=list(dict.fromkeys(k for row in rows for k in row))
with (OUT/'summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
labels={'CONTROL':'原全仓退出','PARTIAL':'2%、3%各减1/3','EARLY_2':'1%、2%各减25%','THREE_3':'2%、3%、4%各减25%','LATE_2':'3%、5%各减25%'}
lines=['# 2020分批档位与比例对照','','实际窗口：2020-02-16至2020-12-31（北京时间），不是全年。缺2019预热，2020全年仍未验证。旧ER、旧六线SMA/EMA20、60、120、0.25%密集阈值、2%绝对支撑阻力距离及其他入场不变。手续费0、杠杆3、每币500USDT、原出场滑点0.02%。','', '档位指相对开仓价顺向涨跌幅，比例均相对初始数量，按原数量步长向下取整。余仓按原阶梯止损。五秒相位2秒轮询产生请求，随后首笔实际成交价格模拟减仓；止损优先。提前1%档专门唤醒相应分钟的逐笔回放，不以K线高点假定达到轮询阈值。','', '|方案|组合收益|最大回撤|BTC收益|ETH收益|开仓|','|---|---:|---:|---:|---:|---:|']
for q in rows:lines.append(f"|{labels[q['profile']]}|{q['return_pct']:+.2f}%|{q['max_drawdown_pct']:.2f}%|{q['BTC_return_pct']:+.2f}%|{q['ETH_return_pct']:+.2f}%|{q['opens']}|")
lines+=['', '原全仓及2%、3%各1/3直接读取之前实际结果，没有重跑。三组新方案事先固定，没有根据中间收益反复搜索；仅用2020窗口评估，不能认定跨年有效或更接近参考机器人。','', '来源：币安USDT永续官方原生K线和真实aggTrades/必要时原始trades，官方SHA256校验；逐笔来源URL和哈希保存在各币目录*_tick_sources.json，复用K线来源见../er_partial_2020/*_candle_sources.json。禁止OHLC回退。资金费、市场深度及实际部分成交未模拟。','', '执行命令：','```sh','/workspace/.venv-btc-eth-original/bin/python -u outputs/er_partial_variants_2020/run_variants.py BTC > outputs/er_partial_variants_2020/BTC_run.log 2>&1','/workspace/.venv-btc-eth-original/bin/python -u outputs/er_partial_variants_2020/run_variants.py ETH > outputs/er_partial_variants_2020/ETH_run.log 2>&1','/workspace/.venv-btc-eth-original/bin/python outputs/er_partial_variants_2020/collect.py','```']
(OUT/'report.md').write_text('\n'.join(lines)+'\n');print(json.dumps(rows,ensure_ascii=False))
