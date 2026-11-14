from pathlib import Path
import json,csv
import numpy as np
OUT=Path(__file__).resolve().parent
reference=json.loads((OUT/'old_reference_from_prior_report.json').read_text())
rows=[]
for year in range(2020,2026):
 for profile in ['M30','H4']:
  row=dict(year=year,profile=profile,old_ER_prior_report_return_pct=reference['annual_return_pct'][str(year)],old_source_file_verified=False)
  files=[OUT/str(year)/f'{a}_{profile}_result.json' for a in ['BTC','ETH']]
  if all(p.exists() for p in files) and all((OUT/str(year)/f'{a}_status.json').exists() and json.loads((OUT/str(year)/f'{a}_status.json').read_text()).get('completed') for a in ['BTC','ETH']):
   qs=[json.loads(p.read_text()) for p in files]
   eq=sum(np.load(OUT/str(year)/f'{a}_{profile}_equity.npy') for a in ['BTC','ETH']);v=np.r_[1000.,eq]
   row.update(status='COMPLETE',return_pct=100*(sum(q['ending_equity'] for q in qs)/1000-1),BTC_return_pct=qs[0]['return_pct'],ETH_return_pct=qs[1]['return_pct'],max_drawdown_pct=float(np.max(100*(1-v/np.maximum.accumulate(v)))),opens=sum(q['opens'] for q in qs))
  else:
   failures=[OUT/str(year)/f'{a}_failure.json' for a in ['BTC','ETH']]
   row.update(status='UNVERIFIED_DATA_FAILURE' if any(p.exists() for p in failures) else 'PENDING',return_pct=None)
   row['failures']='; '.join(json.loads(p.read_text())['error'] for p in failures if p.exists())
  rows.append(row)
fields=list(dict.fromkeys(k for r in rows for k in r))
with (OUT/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
(OUT/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
lines=['# 其他年份：新六MA0.50%＋30分钟/4小时','','仅运行用户指定两组，其他参数不改。旧ER不重跑；旧收益来自此前汇报，原年度结果文件未恢复，因此其来源文件尚未核对。','', '|年份|新＋30分钟收益|新＋4小时收益|旧ER历史汇报值（原文件未核对）|','|---|---:|---:|---:|']
for y in range(2020,2026):
 a=[r for r in rows if r['year']==y];fmt=lambda q:f"{q['return_pct']:+.2f}%" if q['status']=='COMPLETE' else '未验证（数据失败）' if q['status']=='UNVERIFIED_DATA_FAILURE' else '运行中/待执行'
 lines.append(f"|{y}|{fmt(a[0])}|{fmt(a[1])}|{reference['annual_return_pct'][str(y)]:+.2f}%|")
lines+=['','2020所需2019年10月预热行情的官方档案返回HTTP404，没有拼接现货或虚构价格。未完成结果不记为0收益。','', '新版本数据源为Binance USD-M官方K线及逐笔，0手续费、3倍名义仓位、原0.02%出场不利滑点、2%绝对支撑阻力距离；六条SMA5/10/30/60/120/250，原3根前方向比较与96根密集窗口。高周期均为已收盘K线。', '', '执行命令：','```sh','/workspace/.venv-btc-eth-original/bin/python -u outputs/other_years_050/batch.py > outputs/other_years_050/run.log 2>&1','/workspace/.venv-btc-eth-original/bin/python outputs/other_years_050/collect.py','```']
lines += ['', '2024两币均因10月28日官方逐笔与分钟K线不一致而停止，全年未验证。具体样本、哈希及恢复命令见[续测记录](continuation_notes.md)。', '', '旧ER列只作此前汇报值对照，尚未核实原结果文件，不能视为本次已验证基准。']
(OUT/'report.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(rows,ensure_ascii=False))
