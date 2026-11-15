from pathlib import Path
import csv,json,hashlib,datetime
O=Path(__file__).resolve().parent
def read(n):return list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
t=read('totals.csv');d=read('account_difference_reconciliation.csv');a=read('annual.csv');p=O/'CONCLUSION.md'
lead='''# 结论先读

固定A带宽和原算式没有修改。两个宏观冷却组在本次1m OHLC假设路径下改善了七期合计，但都只在2/7个区间提高收益，主要依赖2022，不足以称跨年份稳定优势，也不宣布实盘替换A。2021和2026两组均无账户变化；2023、2025均恶化，2024宏观组合轻微恶化、仅FOMC不变。

ZERO：A合计1227.21 USDT；A_MACRO_60为1357.49（+130.28），A_FOMC_60为1299.55（+72.35）。每边0.05%假设费用：A为-316.43，A_MACRO_60为-201.26（+115.18），A_FOMC_60为-248.23（+68.20），改善保留但三组仍为合计亏损。

释放仓位后接续交易为负贡献：宏观组合7笔（2赢5亏），ZERO净-69.92；仅FOMC4笔（1赢3亏），ZERO净-35.41。扣费分别-69.80、-34.64。所有这些新增成交信号原本已属于固定A，且有原账户占仓证据；没有新增入场条件或按未来盈亏筛选。

ZERO两组均1/7个区间回撤增大（2023）；扣费后宏观组合2/7（2023、2024），仅FOMC1/7（2023）。最差年度回撤虽略下降，不能替代逐年风险比较。

2020紧急决议按官方实际时间纳入：3月3日10:00EST、3月15日17:00EDT；没有错误地记成14:00ET。主窗口包含发布时刻和+60分钟端点，按signal_close_ms屏蔽；不取消旧挂单、不强制平仓。

以下是逐年完整表及归因。2020仅02-16起，2026仅1—10月；所有收益为独立年度重置结果，非跨年复利，资金费0。

'''
body=p.read_text();body+='\n## 完整账户差额分解（USDT）\n\n|费用|组|新增已平|原消失交易净额|匹配单净额变化|未平贡献变化|最终权益差|\n|---|---|---:|---:|---:|---:|---:|\n'
for fee in ['ZERO','ASSUMED_005_SIDE']:
 for g in ['A_MACRO_60','A_FOMC_60']:
  rr=[r for r in d if r['fee_scenario']==fee and r['group']==g];v={k:sum(float(r[k])for r in rr)for k in ['new_closed_net_USDT','absent_A_closed_net_USDT','matched_net_change_USDT','open_contribution_change_USDT','equity_difference_USDT']};body+='|'+fee+'|'+g+'|'+ '|'.join(f'{x:.2f}'for x in v.values())+'|\n'
body+='\n权益差 = 新增已平 − 原消失交易净额 + 匹配单净额变化 + 未平贡献变化。原消失交易净额为负，表示该集合总体净亏，内含盈利和亏损，不能把它全部表述成避免的硬止损。匹配单变化包括账户余额导致的数量变化，不能把单笔USDT变化全部解释成价格风险变化。\n'
p.write_text(lead+body)
manifest={str(p.relative_to(O)):dict(bytes=p.stat().st_size,SHA256=hashlib.sha256(p.read_bytes()).hexdigest())for p in O.rglob('*')if p.is_file()and '__pycache__'not in p.parts and p.name not in ['DELIVERY_MANIFEST.json','publication_receipt.json']};(O/'DELIVERY_MANIFEST.json').write_text(json.dumps(dict(created_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),accounts=84,new_accounts=56,reused_A_accounts=28,files=manifest),indent=2));print('Finalized')
