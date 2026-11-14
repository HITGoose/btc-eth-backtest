from pathlib import Path
import json,csv,math,shutil,hashlib
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent.parent;DEL=ROOT/'outputs/monthly_er_vs_dynamic_2016_2026';DEL.mkdir(exist_ok=True)
rows=json.loads((OUT/'monthly_long.json').read_text());annual=json.loads((OUT/'annual.json').read_text());index={(q['year'],q['month'],q['profile']):q for q in rows}
assert {q['profile'] for q in rows}=={'CONTROL','DYNAMIC'}
for year in range(2016,2027):
 for profile in ('CONTROL','DYNAMIC'):
  if year==2016:
   assert all(index[year,m,profile]['return_pct'] is None for m in range(1,13));continue
  months=range(11,13) if year==2017 else range(1,11) if year==2026 else range(1,13)
  values=[index[year,m,profile]['return_pct'] for m in months]
  assert all(v is not None for v in values),(year,profile,'not completed')
  compounded=100*(math.prod(1+v/100 for v in values)-1)
  target=next(q['return_pct'] for q in annual if q['year']==year and q['profile']==profile)
  assert abs(compounded-target)<1e-7,(year,profile,'monthly reconciliation')
for p in OUT.glob('*/BTC/status.json'):
 year=int(p.parent.parent.name)
 if year==2016:continue
for name in ('report.md','monthly_comparison.csv','monthly_long.json','annual.csv','annual.json','early_alternative_access.json'):
 shutil.copy2(OUT/name,DEL/name)
# Self-contained phone table; no external scripts, charts or network calls.
wide=list(csv.DictReader((OUT/'monthly_comparison.csv').open(encoding='utf-8-sig')))
html='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>每月：原ER与动态</title><style>body{max-width:720px;margin:24px auto;padding:0 16px;font:16px/1.6 system-ui;color:#20252b}h1{font-size:22px}select{font-size:18px;padding:8px;width:100%;margin:8px 0}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}td,th{padding:9px 6px;border-bottom:1px solid #ddd;text-align:right}td:first-child,th:first-child{text-align:left}.up{color:#08744c}.down{color:#b42318}.muted,small{color:#667085}p{margin:12px 0}</style><h1>每月：原ER与动态减仓</h1><small>零手续费 · 3倍 · 每年两币各500 USDT起算</small><select id="year"></select><p id="source"></p><table><thead><tr><th>月份</th><th>原ER全仓</th><th>动态减仓</th></tr></thead><tbody id="body"></tbody></table><p class="muted">原ER：原阶梯止损全仓退出。动态：顺向1%减初始仓位25%，后续已收盘15分钟趋势首次减弱再减25%，余仓按原阶梯止损。</p><p class="muted">2016全年和2017前10个月未取得完整逐笔，标未验证；2017仅11—12月。2026仅1—10月。现货年份为现货价格驱动的合成多空，不是普通现货账户收益，未计借币成本。不同年份市场不全相同，不能视为同一市场连续回测。</p><script>const data=DATA;const annual=ANNUAL;const select=document.getElementById('year');for(let y=2016;y<=2026;y++){const o=document.createElement('option');o.value=y;o.textContent=y+'年';select.appendChild(o)}select.value=2026;function cell(v,status){const t=document.createElement('td');if(v===null||v===undefined||v===''){t.textContent=status==='NOT_TESTED'?'未测试':'未验证';t.className='muted'}else{v=Number(v);t.textContent=(v>=0?'+':'')+v.toFixed(2)+'%';t.className=v>=0?'up':'down'}return t}function render(){const y=Number(select.value),rr=data.filter(r=>Number(r.year)===y),body=document.getElementById('body');body.replaceChildren();document.getElementById('source').textContent=rr[0].market+(y===2026?'；覆盖1—10月':'');for(const r of rr){const tr=document.createElement('tr'),m=document.createElement('td');m.textContent=r.month+'月';tr.appendChild(m);tr.appendChild(cell(r.CONTROL,r.CONTROL_status));tr.appendChild(cell(r.DYNAMIC,r.DYNAMIC_status));body.appendChild(tr)}const tr=document.createElement('tr'),label=document.createElement('th');label.textContent=y===2026?'1—10月收益':y===2017?'11—12月收益':'全年收益';tr.appendChild(label);for(const p of ['CONTROL','DYNAMIC']){const q=annual.find(r=>r.year===y&&r.profile===p);tr.appendChild(cell(q?.return_pct,''))}body.appendChild(tr)}select.onchange=render;render();</script></html>'''
html=html.replace('DATA',json.dumps(wide,ensure_ascii=False).replace('<','\\u003c'),1).replace('ANNUAL',json.dumps(annual,ensure_ascii=False).replace('<','\\u003c'),1)
(DEL/'monthly.html').write_text(html)
manifest=json.loads((ROOT/'outputs/er_dynamic_annual_2019_2026/rule_manifest.json').read_text());assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in manifest['sha256'].items())
(DEL/'validation.json').write_text(json.dumps(dict(versions=['CONTROL','DYNAMIC'],fixed_version_excluded=True,months_reconcile_to_annual=True,unverified_years=[2016],full_years=list(range(2018,2026)),partial_year={'2017':'November-December','2026':'January through October'},dynamic_rule_hash_unchanged=True,execution_logs_directory=str(OUT)),indent=2))
print('Delivered two-version monthly table:',DEL)
