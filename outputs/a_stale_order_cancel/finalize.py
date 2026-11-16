from pathlib import Path
import csv,json,hashlib,datetime
O=Path(__file__).resolve().parent
read=lambda n:list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
d=read('new_disappeared_reconciliation.csv');a=read('annual.csv');paths=[];late=[];extra='\n## 完整账户路径归因\n\n|费用|新增成交N|新增已平净额|消失成交N|直接撤单/其他消失N|消失已平净额|匹配贡献变化|账户总差|\n|---|---:|---:|---:|---:|---:|---:|---:|\n'
for fee in ['ZERO','MAKER_002_SIDE']:
 rr=[r for r in d if r['fee_scenario']==fee];keys=['new_fill_count','new_closed_net_USDT','new_open_contribution_USDT','disappeared_fill_count','disappeared_directly_cancelled_count','disappeared_other_count','disappeared_closed_net_USDT','disappeared_open_contribution_USDT','matched_contribution_difference_USDT','account_difference_USDT'];v={k:sum(float(r[k])for r in rr)for k in keys};assert abs(v['account_difference_USDT']-v['new_closed_net_USDT']-v['new_open_contribution_USDT']+v['disappeared_closed_net_USDT']+v['disappeared_open_contribution_USDT']-v['matched_contribution_difference_USDT'])<1e-7;paths.append(dict(fee_scenario=fee,**v));extra+=f"|{fee}|{v['new_fill_count']:.0f}|{v['new_closed_net_USDT']:.2f}|{v['disappeared_fill_count']:.0f}|{v['disappeared_directly_cancelled_count']:.0f} / {v['disappeared_other_count']:.0f}|{v['disappeared_closed_net_USDT']:.2f}|{v['matched_contribution_difference_USDT']:.2f}|{v['account_difference_USDT']:.2f}|\n"
 rr=[r for r in a if r['asset']=='COMBINED'and r['group']=='A_CANCEL'and r['fee_scenario']==fee and r['period']in ['2023','2024','2025','2026']];total=sum(float(r['account_difference_vs_base_USDT'])for r in rr);best=max(rr,key=lambda r:float(r['account_difference_vs_base_USDT']));value=float(best['account_difference_vs_base_USDT']);late.append(dict(fee_scenario=fee,late_account_difference_USDT=total,largest_positive_difference_year=best['period'],largest_year_difference_USDT=value,other_three_years_difference_USDT=total-value))
for name,rs in [('path_summary.csv',paths),('late_concentration.csv',late)]:
 with(O/name).open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
extra+='\n新增52笔均为已平成交，未新增期末未平贡献；消失50笔中35笔直接撤单，另外15笔因后续占用/订单路径未再成交，不能全算直接撤单。匹配贡献变化包括余额和数量变化，不是独立退出效果。归因金额不等于可直接加回基准的交易收益，但完整实际账户分解严格闭合。\n\n## 后阶段集中度\n\n|费用|2023—2026总差|唯一正贡献年份|该年差|其他三年合计|\n|---|---:|---|---:|---:|\n'
for r in late:extra+=f"|{r['fee_scenario']}|{r['late_account_difference_USDT']:.2f}|{r['largest_positive_difference_year']}|{r['largest_year_difference_USDT']:.2f}|{r['other_three_years_difference_USDT']:.2f}|\n"
lead='''# 结论先读

**不建议保留为正式撤单规则；保留实验记录，A_BASE不改。** 撤掉的基准亏损不足以抵消错过的盈利，完整账户尤其后阶段明显恶化。没有追加等待阈值、两根收盘或新过滤。

每个费用场景163次撤单请求，其中132次实际取消、9次撤前已成交、22次原到期先执行。132次实际撤单中：73次基准最终未成交，17次基准成交亏损，18次成交盈利，0次基准期末未平，24次基准未提交同身份订单（保持未匹配，不伪装未成交）。两费用情景是同类路径对照，不当成264个独立撤单样本。

ZERO撤掉的17笔基准亏损为584.95USDT，错过18笔盈利691.92，直接已成交集合原本净赚106.97，故不足抵消。MAKER相应亏损574.62、盈利644.13，差69.52。每1000初始实际名义的逐笔均值/中位数另列；ZERO亏损组r均-21.52、盈利组+21.90。未成交或基准未提交订单没有实际成交名义，归一化留空，不编造0收益率。

确实存在17笔“等待→闭K失效→变体撤单→基准随后成交→最终亏损”链条；但同样撤掉18笔后来盈利单。被撤且基准成交的35单等待均值33.03分钟、中位34.17；变体有同身份订单但未撤的基准成交850单均值15.59、中位9.13。更长等待是事实，不足以推导该撤单条件有效；未成交未被混入等待均值。

完整七期ZERO：A_BASE2555.35、A_CANCEL2090.75，差-464.60；MAKER：1976.31对1547.65，差-428.65。两费用均仅2/7区间跑赢，4/7回撤扩大。2020—2022差-122.92/-112.57，2023—2026差-341.68/-316.08（ZERO/MAKER）；两个阶段均恶化。

释放占用后新增52笔成交，ZERO净亏230.17，MAKER净亏245.42。另有15笔非直接撤单的原成交消失，ZERO原净利294.10；合并35笔直接撤销的原成交，共50笔原成交消失，原净利401.07。不能只展示撤掉亏损的有利案例。

2024BTC约329天持仓未受撤单影响：基准等待8.5分钟已成交，早于该订单首次可检查的后续15m收盘；变体同身份仍持有至期末，两费用贡献与基准相同。没有保留特例。此次规则只检查未成交订单，持仓后不再检查或提前退出。

只新回放A_CANCEL28个账户，引用经验证一致的A_BASE28个；信号完全不变、fixed/cap5、3x，无A_FAIL_EXIT、V2或动态带宽。保持原1m OHLC事件顺序：原到期优先，再T+60秒撤单，再该分钟价格撮合，已成交请求失效；撤单不收费、不变现金、不立即重挂。

以下给出完整逐年、分币及组合统计。净盈亏含期末未平估值、扣已付未平入场费，未假设未来平仓；2020仅02-16起、2026仅1—10月，年度独立每币500，不拼接复利。零资金费、退出滑点0.02%；MAKER每边0.02%只是费用假设，不保证真实Maker。结果来自15m+1m OHLC模型，不是RAW或新样本外。

'''
p=O/'CONCLUSION.md';p.write_text(lead+p.read_text()+extra);print('Finalized')
