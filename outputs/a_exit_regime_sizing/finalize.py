from pathlib import Path
import csv,json,hashlib,datetime
O=Path(__file__).resolve().parent
read=lambda n:list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
sums=read('totals.csv');risk=read('exposure.csv');annual=read('annual.csv');inventory=json.loads((O/'input_inventory.json').read_text());p=O/'CONCLUSION.md';extra='\n## 额外核算：全期平均敞口与未平贡献\n\n全期平均按每个独立区间实际分钟数加权，只是敞口统计，不是跨年连续账户或跨年回撤。\n\n|费用|组|全期平均组合gross/equity|A_BASE|比值|\n|---|---|---:|---:|---:|\n';agg=[]
for fee in ['ZERO','ASSUMED_005_SIDE','MAKER_002_SIDE']:
 rr=[r for r in risk if r['asset']=='COMBINED'and r['fee_scenario']==fee];means={}
 for group in ['A_BASE','A_EXIT_UNCAPPED','A_EXIT_TRAIL8','A_REGIME_SIZE']:
  r=[x for x in rr if x['group']==group];dur=lambda x:(inventory[x['period']+'_BTC']['end']-inventory[x['period']+'_BTC']['start'])//60;means[group]=sum(float(x['minute_end_avg_gross_equity_leverage'])*dur(x)for x in r)/sum(dur(x)for x in r)
 for group,value in means.items():
  ratio=value/means['A_BASE'];extra+=f'|{fee}|{group}|{value:.4f}|{means["A_BASE"]:.4f}|{ratio:.4f}|\n';agg.append(dict(fee_scenario=fee,group=group,all_period_mean_combined_leverage=value,base_leverage=means['A_BASE'],leverage_ratio_vs_base=ratio))
with(O/'exposure_totals.csv').open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(agg[0]));w.writeheader();w.writerows(agg)
extra+='\n|费用|组|权益净额合计|已平净额合计|期末未平浮盈亏合计|\n|---|---|---:|---:|---:|\n'
for r in sums:extra+=f"|{r['fee_scenario']}|{r['group']}|{float(r['net_pnl_USDT']):.2f}|{float(r['closed_net_USDT']):.2f}|{float(r['end_unrealized_USDT']):.2f}|\n"
extra+='\n权益净额还包含未平仓入场费的现金影响，因此不能只把已平净额与浮盈简单相加而忽略该费用。未对期末仓位假设理想平仓或补扣未来退出费。\n'
p.write_text((O/'SUMMARY_ZH.md').read_text()+p.read_text()+extra)
manifest={str(p.relative_to(O)):dict(bytes=p.stat().st_size,SHA256=hashlib.sha256(p.read_bytes()).hexdigest())for p in O.rglob('*')if p.is_file()and '__pycache__'not in p.parts and p.name not in ['DELIVERY_MANIFEST.json','publication_receipt.json']};(O/'DELIVERY_MANIFEST.json').write_text(json.dumps(dict(created_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=manifest),indent=2));print('Finalized')
