from pathlib import Path
import csv,json,hashlib,datetime
O=Path(__file__).resolve().parent
read=lambda n:list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
a=read('annual.csv');d=read('new_disappeared_reconciliation.csv');pathrows=[];conc=[]
extra='\n## 完整路径的新成交与消失成交\n\n|费用|新增成交N|新增已平净额|新增未平贡献|消失成交N|消失已平净额|消失未平贡献|匹配贡献变化|\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
for fee in ['ZERO','MAKER_002_SIDE']:
 rr=[r for r in d if r['fee_scenario']==fee];keys=['new_fill_count','new_closed_net_USDT','new_open_contribution_USDT','disappeared_fill_count','disappeared_closed_net_USDT','disappeared_open_contribution_USDT','matched_contribution_difference_USDT'];v={k:sum(float(r[k])for r in rr)for k in keys};pathrows.append(dict(fee_scenario=fee,**v));extra+='|'+fee+'|'+'|'.join(f'{v[k]:.2f}'for k in keys)+'|\n'
 rr=[r for r in a if r['asset']=='COMBINED'and r['fee_scenario']==fee and r['group']=='A_FAIL_EXIT'and r['period']in['2023','2024','2025','2026']];total=sum(float(r['account_difference_vs_base_USDT'])for r in rr);best=max(rr,key=lambda r:float(r['account_difference_vs_base_USDT']));b=float(best['account_difference_vs_base_USDT']);conc.append(dict(fee_scenario=fee,late_difference_USDT=total,largest_gain_year=best['period'],largest_year_difference_USDT=b,other_three_years_difference_USDT=total-b,years_late_improved=sum(float(r['account_difference_vs_base_USDT'])>1e-8 for r in rr)))
extra+='\n新增成交包含未平记录，不能把新增已平亏损与新增未平贡献混为同一结果；原消失交易合计为净盈利。完整权益差=新增贡献−消失贡献+匹配贡献变化，均来自完整账户路径，不是把独立提前退出收益加回基准。\n\n## 后阶段集中度\n\n|费用|2023—2026净差额|最大正贡献年份|该年差额|其余三年合计|\n|---|---:|---|---:|---:|\n'
for r in conc:extra+=f"|{r['fee_scenario']}|{r['late_difference_USDT']:.2f}|{r['largest_gain_year']}|{r['largest_year_difference_USDT']:.2f}|{r['other_three_years_difference_USDT']:.2f}|\n"
for name,rs in [('path_summary.csv',pathrows),('late_concentration.csv',conc)]:
 with(O/name).open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
lead='''# 结论先读

**保留实验记录，不建议把A_FAIL_EXIT纳入正式策略或替换A_BASE。** 它确实减少了失败交易损失，但会误杀赢家，完整账户没有跨年份一致改善。没有追加其他持仓小时、带内条件或参数。

每个费用场景实际提前退出200笔：其中106笔基准最终硬止损全部在相同初始名义下减少损失；ZERO同名义改善2990.81USDT，实际账户金额差2955.13。与此同时，ZERO误杀67笔基准已平盈利交易，原利润1935.39，早退后净亏448.45；同名义损害2346.10。MAKER误杀66笔，原利润1824.11，同名义损害2258.07。另有基准其他亏损、3笔基准期末未平和23笔基准没有对应成交的新单，分开列示，未把未平判成最终赢家/输家。

七期ZERO净额：A_BASE2555.35、A_FAIL_EXIT2878.87，差+323.52；MAKER_002_SIDE：1976.31对2204.59，差+228.28。两费用均4/7区间跑赢，同时4/7区间回撤扩大。2023—2026净增益仅ZERO+90.20、MAKER+17.27；其中2024贡献+256.52/+229.56，其他三年合计为负，后阶段增益依赖单一年份。

2024BTC约329天未平仓未被提前退出：检查时方向毛盈亏为正，且两根收盘均不在带内，因此不满足规则，并非保留特例。变体仍持有至期末，数量因前序余额增大；ZERO期末贡献从1799.04增至1955.93，主要是数量变化，而非该笔退出价格改善。

2026明显恶化：ZERO相对基准-237.82USDT、回撤扩大3.03个百分点；MAKER-237.58、回撤扩大2.68个百分点。新成交142笔，ZERO新增已平净亏117.79，另有244.48未平贡献；原消失28笔成交合计净赚250.09。不得只展示减少硬止损的有利部分。

执行解释在回放前冻结：检查T之后下一分钟开盘T+60秒才可执行，期间及同事件原止损优先；不是判断收盘价成交。每笔实际成交后满4小时首个闭15m检查一次，不满足也不重复。使用原六线各自带内判定、原fixed/cap5、原3x与全部完整入场信号。

本轮为15m信号+1m OHLC假设模型，不是RAW或实盘成交。2020仅02-16起、2026仅1—10月，每年每币500独立起算；资金费0、退出滑点0.02%。0.02%费用为每边假设，不保证真实Maker费率。净额含期末未平估值，不把浮盈称作已实现利润，不将七期拼接复利。

'''
p=O/'CONCLUSION.md';p.write_text(lead+p.read_text()+extra)
manifest={str(p.relative_to(O)):dict(bytes=p.stat().st_size,SHA256=hashlib.sha256(p.read_bytes()).hexdigest())for p in O.rglob('*')if p.is_file()and '__pycache__'not in p.parts and p.name not in ['DELIVERY_MANIFEST.json','publication_receipt.json']};(O/'DELIVERY_MANIFEST.json').write_text(json.dumps(dict(created_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=manifest),indent=2));print('Finalized')
