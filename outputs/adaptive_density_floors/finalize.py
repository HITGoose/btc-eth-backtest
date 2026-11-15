from pathlib import Path
import csv,json,hashlib,datetime,collections
O=Path(__file__).resolve().parent
rs=list(csv.DictReader((O/'annual.csv').open(encoding='utf-8-sig')));ss=list(csv.DictReader((O/'signal_attribution.csv').open(encoding='utf-8-sig')));removed=list(csv.DictReader((O/'removed_signals.csv').open(encoding='utf-8-sig')));text='\n## 完整账户比较与限制\n\n'
for fee in ['ZERO','ASSUMED_005_SIDE']:
 aa={(r['period'],r['asset']):r for r in rs if r['group']=='A'and r['fee_scenario']==fee};text+='### '+fee+'\n\n|组|组合收益高于A的区间数|组合回撤大于A的区间数|新增已平交易净额|原盈利单缺失数量/原利润|\n|---|---:|---:|---:|---:|\n'
 for group in ['B','D','E1','E2_030','E2_035','E3_030','E3_035']:
  rr=[r for r in rs if r['group']==group and r['fee_scenario']==fee and r['asset']=='COMBINED'];s=[r for r in ss if r['group']==group and r['fee_scenario']==fee]
  win=sum(float(r['net_pnl_USDT'])>float(aa[r['period'],'COMBINED']['net_pnl_USDT'])for r in rr);dd=sum(float(r['max_drawdown_pct'])>float(aa[r['period'],'COMBINED']['max_drawdown_pct'])for r in rr)
  text+=f"|{group}|{win}/{len(rr)}|{dd}/{len(rr)}|{sum(float(x['new_closed_net_USDT'])for x in s):.2f}|{sum(int(x['original_profitable_trades_absent'])for x in s)} / {sum(float(x['original_profit_absent_USDT'])for x in s):.2f}|\n"
text+='\n旧逐笔账本的281笔移除交易和2026新增56笔诊断已核实，见prior_diagnosis.json；这些旧逐笔利润不是本次K线可直接加回的金额。E3冷却按signal_close_ms过滤，与按opened_ms事后剔除的统计并非同一干预，不能将旧宏观归因金额当作本轮改善保证。\n\n'
text+='E1/E2历史阈值下限不是对所有未来样本的A信号保留数学保证：震荡当前W门槛仍沿B动态值，未来可能低于A的0.50%。本次历史区间的实际移除数另列removed_signals.csv；没有偷偷加入A信号并集或提高当前W门槛。即使信号全保留，占仓、资金路径也可使原盈利成交消失。\n\n'
text+='所选OHLC路径会改变止损、阶梯和限价成交时点。即便某变体在此路径下胜出，也不能当作原始逐笔口径的改进证明。宏观窗口和阈值已被既有历史观察选择，不称新样本外，不按年份选版本。未运行反向OLHC或额外参数搜索，避免扩大本轮任务。\n\n'
text+='运行命令见RUN.md；官方宏观时间及来源见calendar.json；原源码校验见CONFIG.json；必要检查见checks.json；224账户现金对账见cash_checks.csv。\n'
p=O/'CONCLUSION.md';p.write_text(p.read_text()+text)
manifest={str(p.relative_to(O)):dict(bytes=p.stat().st_size,SHA256=hashlib.sha256(p.read_bytes()).hexdigest())for p in O.rglob('*')if p.is_file()and '__pycache__'not in p.parts and p.name!='DELIVERY_MANIFEST.json'}
(O/'DELIVERY_MANIFEST.json').write_text(json.dumps(dict(created_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=manifest),indent=2))
print('FINALIZED',len(rs),'annual rows',len(ss),'attribution rows')
